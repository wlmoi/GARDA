#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
waypoint_global_planner_node.py - Robust Closed-Loop Global Planner & Waypoint Action Server
Part of Project IGOR (Hiwonder JetAuto Mecanum AMR)

Key Capabilities:
1. Implements ROS 2 Action Server for `waypoint_action/action/WaypointSet` compatible with waypoint_client.
2. Supports goal fields: absis, ordinat, yaw, duration.
3. Closed-Loop Tracking: Subscribes to `/pose` (from motion_node or odometry/SLAM), calculates lookahead
   carrot trajectory using GlobalPath / LookaheadCarrotTracker principles.
4. Continuous Feedback: Publishes real-time feedback (absis_feedback, ordinat_feedback, yaw_feedback, progress)
   and handles goal cancellation with safe zero-stop command.
5. Dynamic Speed Adjustments: Allows runtime max_speed / speed_scale reconfiguration without waiting for keypresses.
6. Feeds nominal velocity & target carrot directly into `/cmd_vel_in` for the downstream AI controller node.
"""

import math
import time
from typing import Optional, Tuple
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rcl_interfaces.msg import SetParametersResult, ParameterDescriptor

from geometry_msgs.msg import Twist, PoseStamped
from std_msgs.msg import Bool, Float32

from waypoint_action.action import WaypointSet


def wrap_to_pi(angle_rad: float) -> float:
    """Normalize angle to [-pi, pi]."""
    return math.atan2(math.sin(angle_rad), math.cos(angle_rad))


class WaypointGlobalPlannerNode(Node):
    """
    Robust Global Planner Action Server for Project IGOR.
    Translates discrete or sequence waypoint goals into continuous closed-loop lookahead commands.
    """

    def __init__(self):
        super().__init__("waypoint_global_planner_node")

        # Declare Dynamic Parameters
        self.declare_parameter("cruise_speed", 0.45)
        self.declare_parameter("max_linear_speed", 0.60)
        self.declare_parameter("max_angular_speed", 1.80)
        self.declare_parameter("lookahead_dist", 0.50)
        self.declare_parameter("xy_goal_tolerance", 0.15)
        self.declare_parameter("yaw_goal_tolerance", 0.10)  # ~5.7 degrees
        self.declare_parameter("kp_heading", 2.2)
        self.declare_parameter("kp_lateral", 1.4)
        self.declare_parameter("speed_multiplier", 1.0)

        # Internal Robot State (from /pose or /odom)
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0
        self.has_pose = False
        self.last_pose_time = 0.0

        # Action Server
        self._action_server = ActionServer(
            self,
            WaypointSet,
            "waypoint",
            execute_callback=self.execute_callback,
            cancel_callback=self.cancel_callback,
            goal_callback=self.goal_callback,
        )

        # Publishers
        # Feeds nominal commands to the downstream AI / Safety Gate controller
        self.cmd_vel_in_pub = self.create_publisher(Twist, "/cmd_vel_in", 10)
        # Direct /cmd_vel publisher for compatibility with standalone test setups
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.goal_reached_pub = self.create_publisher(Bool, "/waypoint_goal", 10)
        self.heading_pub = self.create_publisher(Float32, "/igor/planner_heading_err", 10)

        # Subscribers
        self.pose_sub = self.create_subscription(
            PoseStamped,
            "/pose",
            self._pose_callback,
            10
        )

        # Parameter change callback for runtime speed adjustments
        self.add_on_set_parameters_callback(self._on_parameter_change)

        self.get_logger().info("==================================================================")
        self.get_logger().info("  IGOR WAYPOINT GLOBAL PLANNER INITIALIZED")
        self.get_logger().info(f"  Cruise Speed       : {self.get_parameter('cruise_speed').value} m/s")
        self.get_logger().info(f"  Lookahead Distance : {self.get_parameter('lookahead_dist').value} m")
        self.get_logger().info(f"  Goal Tolerance     : {self.get_parameter('xy_goal_tolerance').value} m")
        self.get_logger().info("==================================================================")

    def _on_parameter_change(self, params):
        for param in params:
            if param.name in [
                "cruise_speed", "max_linear_speed", "max_angular_speed",
                "speed_multiplier", "lookahead_dist"
            ]:
                self.get_logger().info(f"Dynamic parameter update: {param.name} -> {param.value}")
        return SetParametersResult(successful=True)

    def _pose_callback(self, msg: PoseStamped):
        """Update robot state from /pose (PoseStamped)."""
        self.robot_x = msg.pose.position.x
        self.robot_y = msg.pose.position.y

        # Quaternion to Euler yaw
        qx = msg.pose.orientation.x
        qy = msg.pose.orientation.y
        qz = msg.pose.orientation.z
        qw = msg.pose.orientation.w
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
        self.robot_yaw = math.atan2(siny_cosp, cosy_cosp)

        self.has_pose = True
        self.last_pose_time = time.time()

    def cancel_callback(self, goal_handle):
        self.get_logger().info("Received cancel request for current waypoint goal.")
        return CancelResponse.ACCEPT

    def goal_callback(self, goal_request):
        self.get_logger().info(
            f"Received goal request: absis={goal_request.absis:.2f}, "
            f"ordinat={goal_request.ordinat:.2f}, yaw={goal_request.yaw:.2f} deg, "
            f"duration={goal_request.duration:.2f}s"
        )
        if goal_request.duration <= 0:
            self.get_logger().warn(f"Rejecting goal: duration must be > 0 (got {goal_request.duration})")
            return GoalResponse.REJECT

        if abs(goal_request.absis) > 100.0 or abs(goal_request.ordinat) > 100.0:
            self.get_logger().warn("Rejecting goal: coordinate out of limits (-100 to 100m)")
            return GoalResponse.REJECT

        return GoalResponse.ACCEPT

    def _stop_robot(self):
        """Publishes zero velocity to immediately halt robot."""
        zero_twist = Twist()
        self.cmd_vel_in_pub.publish(zero_twist)
        self.cmd_vel_pub.publish(zero_twist)

    def compute_closed_loop_twist(
        self,
        target_x: float,
        target_y: float,
        target_yaw_rad: float,
        dist_to_goal: float,
        is_pure_rotation: bool
    ) -> Tuple[float, float, float, float]:
        """
        Computes holonomic body velocities (vx, vy, omega) towards the target waypoint.
        Returns: (cmd_vx, cmd_vy, cmd_omega, heading_err)
        """
        cruise_speed = float(self.get_parameter("cruise_speed").value)
        speed_mult = float(self.get_parameter("speed_multiplier").value)
        max_vx = float(self.get_parameter("max_linear_speed").value) * speed_mult
        max_omega = float(self.get_parameter("max_angular_speed").value) * speed_mult
        kp_heading = float(self.get_parameter("kp_heading").value)
        kp_lateral = float(self.get_parameter("kp_lateral").value)

        rx, ry, ryaw = self.robot_x, self.robot_y, self.robot_yaw

        if is_pure_rotation:
            # Pure rotational movement
            heading_err = wrap_to_pi(target_yaw_rad - ryaw)
            cmd_omega = float(np.clip(kp_heading * heading_err, -max_omega, max_omega))
            return 0.0, 0.0, cmd_omega, heading_err

        # Translational or combined movement
        dx_world = target_x - rx
        dy_world = target_y - ry

        # Smooth deceleration ramp near goal
        effective_speed = cruise_speed * speed_mult
        if dist_to_goal < 0.80:
            effective_speed = max(0.10, effective_speed * (dist_to_goal / 0.80))

        # Convert to robot body frame
        cos_y = math.cos(ryaw)
        sin_y = math.sin(ryaw)
        dx_body = dx_world * cos_y + dy_world * sin_y
        dy_body = -dx_world * sin_y + dy_world * cos_y

        dist_body = math.hypot(dx_body, dy_body)
        if dist_body > 1e-4:
            unit_vx = dx_body / dist_body
            unit_vy = dy_body / dist_body
        else:
            unit_vx, unit_vy = 0.0, 0.0

        cmd_vx = float(np.clip(effective_speed * unit_vx, -0.15, max_vx))
        cmd_vy = float(np.clip(effective_speed * unit_vy * kp_lateral, -0.45, 0.45))

        # Desired heading: either target yaw if specified, or aligned with translation vector
        if abs(target_yaw_rad) > 1e-4:
            heading_err = wrap_to_pi(target_yaw_rad - ryaw)
        else:
            desired_yaw = math.atan2(dy_world, dx_world)
            heading_err = wrap_to_pi(desired_yaw - ryaw)

        cmd_omega = float(np.clip(kp_heading * heading_err, -max_omega, max_omega))

        return cmd_vx, cmd_vy, cmd_omega, heading_err

    async def execute_callback(self, goal_handle):
        """
        Executes waypoint navigation with closed-loop feedback, lookahead carrot tracking,
        timeout guards, and real-time progress reporting.
        """
        target_absis = float(goal_handle.request.absis)
        target_ordinat = float(goal_handle.request.ordinat)
        target_yaw_deg = float(goal_handle.request.yaw)
        target_yaw_rad = math.radians(target_yaw_deg)
        duration = float(goal_handle.request.duration)

        xy_tol = float(self.get_parameter("xy_goal_tolerance").value)
        yaw_tol = float(self.get_parameter("yaw_goal_tolerance").value)

        # Detect pure rotation mode (matching waypoint_list convention where absis=0, ordinat=0, yaw!=0)
        is_pure_rotation = (
            abs(target_absis) < 1e-4 and
            abs(target_ordinat) < 1e-4 and
            abs(target_yaw_deg) > 1e-4
        )

        initial_x = self.robot_x
        initial_y = self.robot_y
        initial_yaw = self.robot_yaw

        total_distance = math.hypot(target_absis - initial_x, target_ordinat - initial_y)
        if is_pure_rotation:
            total_angular_dist = abs(wrap_to_pi(target_yaw_rad - initial_yaw))
        else:
            total_angular_dist = 0.0

        self.get_logger().info(
            f"Starting execution: Target=({target_absis:.2f}, {target_ordinat:.2f}), "
            f"Yaw={target_yaw_deg:.1f}°, DurationLimit={duration:.1f}s, PureRotation={is_pure_rotation}"
        )

        feedback_msg = WaypointSet.Feedback()
        start_time = time.time()
        rate_hz = 20.0
        dt = 1.0 / rate_hz

        # Loop until goal reached, canceled, or timeout exceeded (duration + safety grace period)
        max_duration = duration * 1.5  # Allow 50% grace time for obstacle avoidance detours

        while rclpy.ok():
            # 1. Handle Cancellation
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                self._stop_robot()
                self.get_logger().info("Waypoint goal was canceled by client.")
                result = WaypointSet.Result()
                result.success = False
                result.speed = 0.0
                result.message = "Goal canceled"
                return result

            now = time.time()
            elapsed_time = now - start_time

            # 2. Check Distance & Convergence
            dist_to_goal = math.hypot(target_absis - self.robot_x, target_ordinat - self.robot_y)
            yaw_err = abs(wrap_to_pi(target_yaw_rad - self.robot_yaw))

            # Progress calculation
            if is_pure_rotation:
                progress_ratio = 1.0 - (yaw_err / max(total_angular_dist, 1e-3))
            elif total_distance > 1e-3:
                progress_ratio = 1.0 - (dist_to_goal / total_distance)
            else:
                progress_ratio = 1.0
            progress_ratio = float(np.clip(progress_ratio, 0.0, 1.0))

            # Feedback message
            feedback_msg.absis_feedback = float(self.robot_x)
            feedback_msg.ordinat_feedback = float(self.robot_y)
            feedback_msg.yaw_feedback = float(math.degrees(self.robot_yaw))
            feedback_msg.progress = f"{progress_ratio * 100.0:.1f}%"
            goal_handle.publish_feedback(feedback_msg)

            # Check completion criteria
            goal_reached = False
            if is_pure_rotation:
                if yaw_err <= yaw_tol:
                    goal_reached = True
            else:
                if dist_to_goal <= xy_tol:
                    # If orientation is also commanded, verify yaw tolerance
                    if abs(target_yaw_deg) > 1e-3:
                        if yaw_err <= yaw_tol:
                            goal_reached = True
                    else:
                        goal_reached = True

            if goal_reached:
                self._stop_robot()
                goal_handle.succeed()
                self.goal_reached_pub.publish(Bool(data=True))
                self.get_logger().info(f"Waypoint successfully reached in {elapsed_time:.2f}s!")
                result = WaypointSet.Result()
                result.success = True
                result.speed = float(self.get_parameter("cruise_speed").value)
                result.message = "Waypoint reached successfully."
                return result

            # Check timeout
            if elapsed_time > max_duration:
                self._stop_robot()
                goal_handle.abort()
                self.get_logger().warn(f"Waypoint goal timed out after {elapsed_time:.2f}s.")
                result = WaypointSet.Result()
                result.success = False
                result.speed = 0.0
                result.message = f"Goal timed out after {elapsed_time:.2f}s"
                return result

            # 3. Compute and Publish Closed-Loop Twist Command
            cmd_vx, cmd_vy, cmd_omega, heading_err = self.compute_closed_loop_twist(
                target_x=target_absis,
                target_y=target_ordinat,
                target_yaw_rad=target_yaw_rad,
                dist_to_goal=dist_to_goal,
                is_pure_rotation=is_pure_rotation
            )

            twist = Twist()
            twist.linear.x = cmd_vx
            twist.linear.y = cmd_vy
            twist.angular.z = cmd_omega

            self.cmd_vel_in_pub.publish(twist)
            self.cmd_vel_pub.publish(twist)

            heading_msg = Float32()
            heading_msg.data = float(heading_err)
            self.heading_pub.publish(heading_msg)

            time.sleep(dt)

        self._stop_robot()
        result = WaypointSet.Result()
        result.success = False
        result.message = "ROS context shutdown"
        return result


def main(args=None):
    rclpy.init(args=args)
    node = WaypointGlobalPlannerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

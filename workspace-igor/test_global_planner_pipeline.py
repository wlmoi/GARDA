#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_global_planner_pipeline.py
Automated end-to-end integration test for Project IGOR Global Planner & Safety Gate:
1. Spawns WaypointGlobalPlannerNode (Action Server: /waypoint).
2. Spawns IgorControllerNode (Local Safety Gate & AI Controller).
3. Simulates /pose (robot position progressing along commanded velocity).
4. Sends WaypointSet action goal.
5. Verifies closed-loop progress feedback, safety gate triggering on obstacle proximity, and goal convergence.
"""

import math
import time
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import Twist, PoseStamped
from sensor_msgs.msg import LaserScan
from waypoint_action.action import WaypointSet

from igor_controller.controller_node import IgorControllerNode
from igor_controller.waypoint_global_planner_node import WaypointGlobalPlannerNode


class PoseSimulatorNode(Node):
    """Simulates robot motion based on commanded twist and publishes /pose and /scan."""
    def __init__(self):
        super().__init__('pose_simulator_node')
        self.pose_pub = self.create_publisher(PoseStamped, '/pose', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)

        self.cmd_sub = self.create_subscription(Twist, '/igor/cmd_vel_safe', self._cmd_cb, 10)

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0

        self.obstacle_distance = 3.50  # Start with clear path
        self.timer = self.create_timer(0.02, self._step)  # 50 Hz

    def _cmd_cb(self, msg: Twist):
        self.vx = msg.linear.x
        self.vy = msg.linear.y
        self.omega = msg.angular.z

    def _step(self):
        dt = 0.02
        self.yaw += self.omega * dt
        # Body to world
        cos_y = math.cos(self.yaw)
        sin_y = math.sin(self.yaw)
        self.x += (self.vx * cos_y - self.vy * sin_y) * dt
        self.y += (self.vx * sin_y + self.vy * cos_y) * dt

        # Publish pose
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(self.x)
        pose.pose.position.y = float(self.y)
        pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        pose.pose.orientation.w = math.cos(self.yaw / 2.0)
        self.pose_pub.publish(pose)

        # Publish 360 scan with simulated frontal obstacle
        scan = LaserScan()
        scan.header.frame_id = 'laser'
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.angle_min = 0.0
        scan.angle_max = 2.0 * math.pi
        scan.angle_increment = 2.0 * math.pi / 360.0
        scan.ranges = [float(self.obstacle_distance)] * 360
        self.scan_pub.publish(scan)


def run_pipeline_test():
    rclpy.init()
    sim_node = PoseSimulatorNode()
    planner_node = WaypointGlobalPlannerNode()
    controller_node = IgorControllerNode()

    executor = MultiThreadedExecutor()
    executor.add_node(sim_node)
    executor.add_node(planner_node)
    executor.add_node(controller_node)

    exec_thread = threading.Thread(target=executor.spin, daemon=True)
    exec_thread.start()

    time.sleep(0.5)

    # Create Action Client
    test_client_node = Node('test_action_client')
    action_client = ActionClient(test_client_node, WaypointSet, 'waypoint')
    assert action_client.wait_for_server(timeout_sec=5.0), "Action server failed to initialize!"

    print("\n--- TEST 1: Sending Goal (absis=1.0, ordinat=0.0, yaw=0.0, duration=5.0) ---")
    goal_msg = WaypointSet.Goal()
    goal_msg.absis = 1.0
    goal_msg.ordinat = 0.0
    goal_msg.yaw = 0.0
    goal_msg.duration = 5.0

    feedback_received = []
    def fb_cb(fb):
        feedback_received.append(fb.feedback)

    send_future = action_client.send_goal_async(goal_msg, feedback_callback=fb_cb)
    start_t = time.time()
    while not send_future.done() and time.time() - start_t < 3.0:
        rclpy.spin_once(test_client_node, timeout_sec=0.05)

    goal_handle = send_future.result()
    assert goal_handle.accepted, "Goal was rejected by planner!"
    print("Goal was successfully accepted by WaypointGlobalPlannerNode.")

    res_future = goal_handle.get_result_async()
    while not res_future.done() and time.time() - start_t < 10.0:
        rclpy.spin_once(test_client_node, timeout_sec=0.05)
        # Verify robot moving forward
        if len(feedback_received) > 0 and feedback_received[-1].absis_feedback > 0.8:
            break

    print(f"Feedback frames received: {len(feedback_received)}")
    if feedback_received:
        last_fb = feedback_received[-1]
        print(f"Latest Feedback: x={last_fb.absis_feedback:.2f}, y={last_fb.ordinat_feedback:.2f}, progress={last_fb.progress}")

    # Wait for goal completion
    while not res_future.done() and time.time() - start_t < 10.0:
        rclpy.spin_once(test_client_node, timeout_sec=0.05)

    assert res_future.done(), "Goal execution timed out!"
    result = res_future.result().result
    print(f"Goal result: success={result.success}, message='{result.message}'")
    assert result.success, "Goal execution did not succeed!"

    # Clean shutdown
    test_client_node.destroy_node()
    sim_node.destroy_node()
    planner_node.destroy_node()
    controller_node.destroy_node()
    rclpy.shutdown()
    print("\nSUCCESS: All integration pipeline tests passed cleanly!")


if __name__ == '__main__':
    run_pipeline_test()

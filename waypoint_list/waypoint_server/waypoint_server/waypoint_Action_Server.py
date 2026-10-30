#!/usr/bin/env python3
import time, numpy as np, math
import rclpy
from rclpy.node import Node
from waypoint_action.action import WaypointSet
from std_msgs.msg import Bool
from geometry_msgs.msg import Twist, PoseStamped
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionServer, CancelResponse, GoalResponse

class waypointActionServer(Node): 
    def __init__(self):
        super().__init__("waypoint_action_server")
        self.angular = 0.0  # Current orientation in radians (from motion node)
        self.absis = 0.0
        self.ordinat = 0.0

        self.goal = WaypointSet.Goal()

        self._action_server = ActionServer(
            self,
            WaypointSet,
            "waypoint",
            execute_callback=self.execute_callback,
            cancel_callback=self.cancel_callback,
            goal_callback=self.goal_callback,
        )
        self.get_logger().info("Waypoint Action Server is ready.")

        # self.speed_pub = self.create_publisher(
        #     Twist, 
        #     'speed',
        #     10)
        
        # self.yaw_pub = self.create_publisher(
        #     Twist,
        #     'yaw', 
        #     10)
        
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            'cmd_vel',
            10
        )

        self.goal_pub = self.create_publisher(
            Bool,
            'waypoint_goal',
            10
        )

        # Subscribe to robot pose for accurate orientation tracking
        # self.pose_sub = self.create_subscription(
        #     PoseStamped,
        #     '/pose',
        #     self.pose_callback,
        #     10
        # )

    # def pose_callback(self, msg):
    #     """Update robot position and orientation from motion node"""
    #     self.absis = msg.pose.position.x
    #     self.ordinat = msg.pose.position.y
        
    #     # Convert quaternion to euler angle (yaw only)
    #     # q = [x, y, z, w] -> yaw = atan2(2*(w*z + x*y), 1 - 2*(y² + z²))
    #     x = msg.pose.orientation.x
    #     y = msg.pose.orientation.y
    #     z = msg.pose.orientation.z
    #     w = msg.pose.orientation.w
        
    #     # Simple conversion for 2D: yaw from quaternion
    #     self.angular = 2 * math.atan2(z, w)  # This is yaw in radians

    def destroy(self):
        self._action_server.destroy()
        super().destroy()
    
    def cancel_callback(self, goal_handle):
        self.get_logger().info("Received cancel request")
        return CancelResponse.ACCEPT
    
    def goal_callback(self, goal_request):
        if goal_request.yaw == 0.0:
            self.get_logger().info(f"Received goal request: absis={goal_request.absis}, ordinat={goal_request.ordinat}, duration={goal_request.duration}")
        else:
            self.get_logger().info(f"Received goal request: yaw={goal_request.yaw}, duration={goal_request.duration}")
        
        # Validasi goal request
        if goal_request.duration <= 0:
            self.get_logger().warn(f"Rejecting goal: duration must be positive (got {goal_request.duration})")
            return GoalResponse.REJECT
        
        if abs(goal_request.absis) > 100 or abs(goal_request.ordinat) > 100:
            self.get_logger().warn(f"Rejecting goal: coordinates out of bounds (absis={goal_request.absis}, ordinat={goal_request.ordinat})")
            return GoalResponse.REJECT
        
        if abs(goal_request.yaw) >= 360:
            self.get_logger().warn(f"Rejecting goal: yaw out of bounds (yaw={goal_request.yaw})")
            return GoalResponse.REJECT
        
        self.get_logger().info("Accepting goal request")
        return GoalResponse.ACCEPT
    
    async def execute_callback(self, goal_handle):
        self.get_logger().info("Executing waypoint action...")

        absis = goal_handle.request.absis
        ordinat = goal_handle.request.ordinat
        duration = goal_handle.request.duration
        yaw = goal_handle.request.yaw

        feedback_msg = WaypointSet.Feedback()
        feedback_msg.absis_feedback = absis
        feedback_msg.ordinat_feedback = ordinat
        feedback_msg.yaw_feedback = yaw

        rate = 0.1
        curret_time = 0.0
        start_time = time.time()
        linier = self.speed_linier(self.absis, absis, self.ordinat, ordinat, duration)
        angular = self.yaw_angular(yaw, duration)

        # Store initial position for feedback interpolation
        initial_absis = self.absis
        initial_ordinat = self.ordinat
        dx = absis - initial_absis
        dy = ordinat - initial_ordinat

        while curret_time < duration:
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                # STOP ROBOT when canceled
                stop_twist = Twist()
                stop_twist.linear.x = 0.0
                stop_twist.linear.y = 0.0
                stop_twist.angular.z = 0.0
                self.cmd_vel_pub.publish(stop_twist)
                self.get_logger().info('Goal canceled')
                result = WaypointSet.Result()
                result.success = False
                result.speed = 0.0
                result.message = "Goal was canceled"
                return result

            current_time = time.time() - start_time
            ratio = min(current_time / duration, 1.0)

            # Linear interpolation from initial position to goal position
            feedback_msg.absis_feedback = initial_absis + (ratio * dx)
            feedback_msg.ordinat_feedback = initial_ordinat + (ratio * dy)
            feedback_msg.yaw_feedback = (ratio * yaw + self.angular)%360
            feedback_msg.progress = f"{ratio*100:.1f}%"
            goal_handle.publish_feedback(feedback_msg)
            self.cmd_vel_callback(linier, angular)
            time.sleep(rate)
            curret_time += rate

        # NOTE: self.angular is now tracked via pose_callback from motion node
        # It reflects actual robot orientation, no need to manually update

        # STOP ROBOT: Publish zero velocity to stop motion
        stop_twist = Twist()
        stop_twist.linear.x = 0.0
        stop_twist.linear.y = 0.0
        stop_twist.angular.z = 0.0
        self.cmd_vel_pub.publish(stop_twist)
        time.sleep(0.1)  # Ensure message is sent

        goal_handle.succeed()
        self.goal_pub.publish(Bool(data=True))

        result = WaypointSet.Result()
        result.success = True
        result.message = "Waypoint reached successfully."

        self.get_logger().info("Waypoint action completed successfully.")
        return result

    def speed_linier(self, absis1, absis2, ordinat1, ordinat2, duration):
        """
        Calculate linear velocity command.
        Transforms global coordinates to robot frame based on current orientation.
        """
        twist = Twist()
        dx = absis2 - absis1
        dy = ordinat2 - ordinat1
        
        # Current robot orientation in radians
        theta = self.angular
        
        # Transform velocity from global frame to robot frame
        # Robot frame: x = forward, y = left
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        
        # Global to robot frame transformation
        vx = (dx * cos_theta) + (dy * sin_theta)
        vy = (-dx * sin_theta) + (dy * cos_theta)
        
        # Divide by duration to get velocity
        twist.linear.x = vx / duration
        twist.linear.y = vy / duration
        return twist
    
    def yaw_angular(self, yaw, duration):
        """
        Calculate angular velocity for rotation.
        yaw: rotation in degrees
        duration: time in seconds
        returns: Twist with omega in radians/second
        """
        twist = Twist()
        # Convert yaw from degrees to radians
        yaw_rad = math.radians(yaw)
        # Calculate angular velocity in rad/s
        omega = yaw_rad / duration
        twist.angular.z = omega
        return twist
    
    def cmd_vel_callback(self, linier, angular):
        cmd_vel = Twist()
        cmd_vel.linear.x = linier.linear.x
        cmd_vel.linear.y = linier.linear.y
        cmd_vel.angular.z = angular.angular.z
        self.cmd_vel_pub.publish(cmd_vel)
    
def main(args=None):
    rclpy.init(args=args)

    node = waypointActionServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    executor.spin()

    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
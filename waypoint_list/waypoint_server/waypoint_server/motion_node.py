#!/usr/bin/env python3
import numpy as np
import math
import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist, PoseStamped, TransformStamped
from nav_msgs.msg import Path
from tf2_ros import TransformBroadcaster


class MotionNode(Node):
    """
    Node untuk mengupdate pose robot berdasarkan command gerakan (Twist messages)
    dan publish pose untuk visualisasi di Rviz
    """

    def __init__(self):
        super().__init__('motion_node')

        # Parameter waktu update
        self.dt = 0.05  # 50ms

        # State robot
        self.pose = np.array([0.0, 0.0])  # [x, y]
        self.theta = 0.0  # orientasi (yaw) dalam radian

        # Velocity command
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0

        # Timeout untuk stop robot jika tidak ada command
        self.last_speed_update = None
        self.last_yaw_update = None
        self.cmd_timeout = 1.0  # 1 detik timeout


        # Subscriber untuk speed (linear motion)
        self.speed_sub = self.create_subscription(
            Twist,
            'speed',
            self.speed_callback,
            10
        )

        # Subscriber untuk yaw (angular motion)
        self.yaw_sub = self.create_subscription(
            Twist,
            'yaw',
            self.yaw_callback,
            10
        )

        # Publisher untuk pose
        self.pose_pub = self.create_publisher(
            PoseStamped,
            '/pose',
            10
        )

        # Publisher untuk path (trajectory)
        self.path_pub = self.create_publisher(
            Path,
            '/path',
            10
        )

        # TF Broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)

        # Path untuk menyimpan trajectory
        self.path = Path()
        self.path.header.frame_id = 'map'

        # Timer untuk update pose
        self.timer = self.create_timer(self.dt, self.update_pose)

        self.get_logger().info('Motion Node initialized')

    def speed_callback(self, msg):
        """Callback untuk menerima linear velocity command"""
        self.vx = msg.linear.x
        self.vy = msg.linear.y
        self.last_speed_update = self.get_clock().now()

    def yaw_callback(self, msg):
        """Callback untuk menerima angular velocity command"""
        self.omega = msg.angular.z
        self.last_yaw_update = self.get_clock().now()

    def update_pose(self):
        """Update pose robot berdasarkan velocity commands"""

        # Check timeout - if no command received in cmd_timeout, stop robot
        current_time = self.get_clock().now()
        
        if self.last_speed_update is not None:
            time_since_speed = (current_time - self.last_speed_update).nanoseconds / 1e9
            if time_since_speed > self.cmd_timeout:
                self.vx = 0.0
                self.vy = 0.0
        
        if self.last_yaw_update is not None:
            time_since_yaw = (current_time - self.last_yaw_update).nanoseconds / 1e9
            if time_since_yaw > self.cmd_timeout:
                self.omega = 0.0

        # Update orientation
        self.theta += self.omega * self.dt

        # Normalize theta ke [-π, π]
        self.theta = np.arctan2(np.sin(self.theta), np.cos(self.theta))

        # Update position (dalam robot frame)
        # Transform velocity dari robot frame ke world frame
        cos_theta = np.cos(self.theta)
        sin_theta = np.sin(self.theta)

        # Velocity di world frame
        vx_world = self.vx * cos_theta - self.vy * sin_theta
        vy_world = self.vx * sin_theta + self.vy * cos_theta

        # Update position
        self.pose[0] += vx_world * self.dt
        self.pose[1] += vy_world * self.dt

        # Publish pose
        self.publish_pose()

        # Publish path
        self.publish_path()

        # Publish TF
        self.publish_tf()

    def publish_pose(self):
        """Publish pose message untuk Rviz"""
        pose_msg = PoseStamped()
        pose_msg.header.frame_id = 'map'
        pose_msg.header.stamp = self.get_clock().now().to_msg()

        # Position
        pose_msg.pose.position.x = float(self.pose[0])
        pose_msg.pose.position.y = float(self.pose[1])
        pose_msg.pose.position.z = 0.0

        # Orientation (quaternion dari yaw)
        # q = [x, y, z, w] = [0, 0, sin(θ/2), cos(θ/2)]
        pose_msg.pose.orientation.x = 0.0
        pose_msg.pose.orientation.y = 0.0
        pose_msg.pose.orientation.z = np.sin(self.theta / 2.0)
        pose_msg.pose.orientation.w = np.cos(self.theta / 2.0)

        self.pose_pub.publish(pose_msg)

    def publish_path(self):
        """Publish path message untuk menampilkan trajectory"""
        # Ambil last pose message
        pose_msg = PoseStamped()
        pose_msg.header.frame_id = 'map'
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.pose.position.x = float(self.pose[0])
        pose_msg.pose.position.y = float(self.pose[1])
        pose_msg.pose.position.z = 0.0
        pose_msg.pose.orientation.x = 0.0
        pose_msg.pose.orientation.y = 0.0
        pose_msg.pose.orientation.z = np.sin(self.theta / 2.0)
        pose_msg.pose.orientation.w = np.cos(self.theta / 2.0)

        # Update path
        self.path.header.stamp = pose_msg.header.stamp
        self.path.poses.append(pose_msg)

        self.path_pub.publish(self.path)

    def publish_tf(self):
        """Publish TF dari map ke base_link"""
        tf = TransformStamped()
        tf.header.frame_id = 'map'
        tf.header.stamp = self.get_clock().now().to_msg()
        tf.child_frame_id = 'base_link'

        # Translation
        tf.transform.translation.x = float(self.pose[0])
        tf.transform.translation.y = float(self.pose[1])
        tf.transform.translation.z = 0.0

        # Rotation (quaternion)
        tf.transform.rotation.x = 0.0
        tf.transform.rotation.y = 0.0
        tf.transform.rotation.z = np.sin(self.theta / 2.0)
        tf.transform.rotation.w = np.cos(self.theta / 2.0)

        self.tf_broadcaster.sendTransform(tf)


def main(args=None):
    rclpy.init(args=args)
    node = MotionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

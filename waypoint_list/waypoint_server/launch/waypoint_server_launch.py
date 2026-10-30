#!/usr/bin/env python3
import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directory
    waypoint_server_dir = get_package_share_directory('waypoint_server')
    rviz_config_path = os.path.join(waypoint_server_dir, 'rviz', 'waypoint_config.rviz')

    return LaunchDescription([
        # Waypoint Action Server
        Node(
            package='waypoint_server',
            executable='waypoint_server_node',
            name='waypoint_server',
            output='screen',
        ),

        # Waypoint Subscriber
        Node(
            package='waypoint_server',
            executable='waypoint_subscriber_node',
            name='waypoint_subscriber',
            output='screen',
        ),

        # # Motion Node (untuk update pose berdasarkan velocity commands)
        # Node(
        #     package='waypoint_server',
        #     executable='motion_node',
        #     name='motion_node',
        #     output='screen',
        # ),

        # # Rviz Visualization
        # Node(
        #     package='rviz2',
        #     executable='rviz2',
        #     name='rviz2',
        #     arguments=['-d', rviz_config_path],
        #     output='screen',
        # ),
    ])
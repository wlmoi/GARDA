"""Route publisher only; hardware controller/localization are separate prerequisites."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('armed', default_value='false'),
        DeclareLaunchArgument('measured_pose_confirmed', default_value='false'),
        DeclareLaunchArgument('pose_topic', default_value='/pose'),
        Node(package='igor_controller', executable='rectangle_route', output='screen',
             name='igor_rectangle_route', parameters=[
                 os.path.join(get_package_share_directory('igor_bringup'), 'config', 'rectangle_5x4_left.yaml'),
                 {'armed': LaunchConfiguration('armed'),
                  'measured_pose_confirmed': LaunchConfiguration('measured_pose_confirmed'),
                  'pose_topic': LaunchConfiguration('pose_topic')}])
    ])

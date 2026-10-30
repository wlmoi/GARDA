#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bringup.launch.py - Master Single-Command Bringup Launch File
Target Platform: Hiwonder JetAuto Mecanum AMR (Jetson Orin Nano + STM32 + RPLiDAR A1 + DE10-Nano)
PERURI Chip Hackathon 2026 - Project IGOR

Usage:
  ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_cbf use_fpga:=false
  ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl use_fpga:=true
  ros2 launch igor_bringup bringup.launch.py algorithm:=dwa use_fpga:=false
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, GroupAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Declare Launch Arguments
    algo_arg = DeclareLaunchArgument(
        'algorithm',
        default_value='cl_drl_cbf',
        description='Obstacle avoidance algorithm: cl_drl, cl_drl_cbf, cl_drl_dwa, dwa, apf'
    )

    use_fpga_arg = DeclareLaunchArgument(
        'use_fpga',
        default_value='false',
        description='Enable DE10-Nano FPGA hardware acceleration (strictly for cl_drl variants)'
    )

    mcu_port_arg = DeclareLaunchArgument(
        'mcu_port',
        default_value='/dev/ttyACM0',
        description='Serial port for JetAuto STM32 chassis controller'
    )

    fpga_port_arg = DeclareLaunchArgument(
        'fpga_port',
        default_value='udp://192.168.50.2:8080',
        description='Ethernet UDP or UART endpoint for DE10-Nano (default matches eth_direction.md)'
    )

    fpga_baudrate_arg = DeclareLaunchArgument(
        'fpga_baudrate',
        default_value='921600',
        description='Direct UART baud rate; must match the programmed FPGA image'
    )

    fpga_timeout_arg = DeclareLaunchArgument(
        'fpga_timeout',
        default_value='0.3',
        description='FPGA transaction deadline in seconds; freshness guards still apply'
    )

    freshness_arg = DeclareLaunchArgument(
        'sensor_freshness_timeout_ms', default_value='25.0',
        description='Maximum sensor age; supervised timed test uses 150 ms for measured 74 ms scans'
    )

    lidar_port_arg = DeclareLaunchArgument(
        'lidar_port',
        default_value='/dev/lidar',
        description='Serial port for Slamtec RPLiDAR A1/A2'
    )

    launch_lidar_arg = DeclareLaunchArgument(
        'launch_lidar',
        default_value='true',
        description='Whether to launch the RPLiDAR serial driver node'
    )

    use_mock_serial_arg = DeclareLaunchArgument(
        'use_mock_serial',
        default_value='false',
        description='Operate serial drivers in mock/simulation mode if physical ports are absent'
    )

    control_rate_arg = DeclareLaunchArgument(
        'control_rate_hz',
        default_value='50.0',
        description='Control loop frequency in Hz'
    )

    launch_planner_arg = DeclareLaunchArgument(
        'launch_planner',
        default_value='true',
        description='Whether to launch the Igor Waypoint Global Planner Action Server'
    )

    # Launch Configurations
    algorithm = LaunchConfiguration('algorithm')
    use_fpga = LaunchConfiguration('use_fpga')
    mcu_port = LaunchConfiguration('mcu_port')
    fpga_port = LaunchConfiguration('fpga_port')
    fpga_baudrate = LaunchConfiguration('fpga_baudrate')
    fpga_timeout = LaunchConfiguration('fpga_timeout')
    lidar_port = LaunchConfiguration('lidar_port')
    launch_lidar = LaunchConfiguration('launch_lidar')
    launch_planner = LaunchConfiguration('launch_planner')
    use_mock_serial = LaunchConfiguration('use_mock_serial')
    control_rate_hz = LaunchConfiguration('control_rate_hz')

    # RPLiDAR Driver Node
    # Physical scans use the installed SLAMTEC driver verified on this robot.
    # The custom synthetic publisher is selected only in explicit mock mode.
    physical_lidar_node = Node(
        package='rplidar_ros',
        executable='rplidar_node',
        name='rplidar_node',
        output='screen',
        parameters=[{
            'serial_port': lidar_port,
            'serial_baudrate': 115200,
            'frame_id': 'laser',
            'angle_compensate': True,
        }],
        condition=UnlessCondition(use_mock_serial)
    )
    mock_lidar_node = Node(
        package='igor_bringup',
        executable='rplidar_driver',
        name='rplidar_driver_node',
        output='screen',
        parameters=[{
            'serial_port': lidar_port,
            'serial_baudrate': 115200,
            'frame_id': 'laser',
            'mock': True
        }],
        condition=IfCondition(use_mock_serial)
    )
    rplidar_node = GroupAction(
        actions=[physical_lidar_node, mock_lidar_node],
        condition=IfCondition(launch_lidar)
    )

    # Igor Controller Node
    controller_node = Node(
        package='igor_controller',
        executable='controller_node',
        name='igor_controller_node',
        output='screen',
        parameters=[{
            'algorithm': algorithm,
            'use_fpga': use_fpga,
            'mcu_port': mcu_port,
            'fpga_port': fpga_port,
            'fpga_baudrate': fpga_baudrate,
            'fpga_timeout': fpga_timeout,
            'sensor_freshness_timeout_ms': LaunchConfiguration('sensor_freshness_timeout_ms'),
            'control_rate_hz': control_rate_hz,
            'use_mock_serial': use_mock_serial
        }]
    )

    # Igor Waypoint Global Planner Node
    planner_node = Node(
        package='igor_controller',
        executable='waypoint_global_planner_node',
        name='waypoint_global_planner_node',
        output='screen',
        parameters=[{
            'cruise_speed': 0.45,
            'max_linear_speed': 0.60,
            'max_angular_speed': 1.80,
            'lookahead_dist': 0.50,
            'xy_goal_tolerance': 0.15,
            'yaw_goal_tolerance': 0.10
        }],
        condition=IfCondition(launch_planner)
    )

    return LaunchDescription([
        algo_arg,
        use_fpga_arg,
        mcu_port_arg,
        fpga_port_arg,
        fpga_baudrate_arg,
        fpga_timeout_arg,
        freshness_arg,
        lidar_port_arg,
        launch_lidar_arg,
        launch_planner_arg,
        use_mock_serial_arg,
        control_rate_arg,
        LogInfo(msg="================================================================"),
        LogInfo(msg="   LAUNCHING PROJECT IGOR AUTONOMOUS JETAUTO NAVIGATION STACK   "),
        LogInfo(msg="================================================================"),
        rplidar_node,
        controller_node,
        planner_node
    ])

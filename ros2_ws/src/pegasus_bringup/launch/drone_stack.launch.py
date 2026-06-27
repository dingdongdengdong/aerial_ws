"""
Pegasus AI — Full Drone Stack Bringup
======================================
Launches the complete simulation stack:
  1. PX4 SITL (flight controller) — started separately
  2. MAVROS (MAVLink↔ROS2 bridge)
  3. AAS aircraft control nodes + repo-owned inspection inference

Usage:
  # Terminal 1: Start PX4 SITL
  cd /workspace/PX4-Autopilot
  make px4_sitl none

  # Terminal 2: Launch full stack
  source /opt/ros/humble/setup.bash
  source /workspace/aerial_ws/ros2_ws/install/setup.bash
  ros2 launch pegasus_bringup drone_stack.launch.py

  # Terminal 3 (optional): Send AAS actions under /Drone1
  ros2 action list
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # ── Arguments ──────────────────────────────────────────────────
    drone_id = LaunchConfiguration("drone_id", default="1")
    drone_namespace = LaunchConfiguration("drone_namespace", default="/Drone1")
    fcu_url = LaunchConfiguration("fcu_url", default="udp://:14540@localhost:18570")
    gcs_url = LaunchConfiguration("gcs_url", default="udp://:@localhost:14550")
    tgt_system = LaunchConfiguration("tgt_system", default="1")
    mission_file = LaunchConfiguration(
        "mission_file",
        default=os.path.join(
            get_package_share_directory("pegasus_bringup"),
            "../../../missions/crane_inspection_demo.yaml",
        ),
    )

    # ── MAVROS node ────────────────────────────────────────────────
    mavros_node = Node(
        package="mavros",
        executable="mavros_node",
        name="mavros",
        parameters=[
            {
                "fcu_url": fcu_url,
                "gcs_url": gcs_url,
                "tgt_system": tgt_system,
                "plugin_allowlist": [
                    "sys_status",
                    "command",
                    "setpoint_position",
                    "setpoint_raw",
                    "local_position",
                    "global_position",
                    "imu",
                    "param",
                    "home_position",
                    "manual_control",
                ],
            }
        ],
        output="screen",
        emulate_tty=True,
    )

    # ── AAS aircraft control nodes ─────────────────────────────────
    autopilot_node = Node(
        package="autopilot_interface",
        executable="px4_interface",
        name="px4_interface",
        namespace=drone_namespace,
        output="screen",
        emulate_tty=True,
    )

    offboard_node = Node(
        package="offboard_control",
        executable="px4_offboard",
        name="px4_offboard",
        namespace=drone_namespace,
        output="screen",
        emulate_tty=True,
    )

    state_sharing_node = Node(
        package="state_sharing",
        executable="state_sharing_node",
        name="state_sharing_node",
        parameters=[{"autopilot": "px4", "drone_id": drone_id}],
        output="screen",
        emulate_tty=True,
    )

    traffic_client_node = Node(
        package="drone_traffic_client",
        executable="dtc_client",
        name="dtc_client",
        output="screen",
        emulate_tty=True,
    )

    mission_node = Node(
        package="mission",
        executable="mission",
        name="mission",
        namespace=drone_namespace,
        arguments=["--conops", mission_file],
        output="screen",
        emulate_tty=True,
    )

    # ── AI Inference node (mock mode for testing) ──────────────────
    inference_node = Node(
        package="pegasus_ai",
        executable="inference_node",
        name="defect_inference",
        parameters=[
            {
                "model_type": "mock",
                "input_image_topic": "/drone/inspection_camera/color/image_raw",
                "output_detections_topic": "/pegasus/ai/defect_detections",
                "output_defect_array_topic": "/pegasus/ai/defect_array",
                "output_json_topic": "/pegasus/ai/defect_json",
                "output_health_topic": "/pegasus/ai/node_health",
                "max_publish_rate": 10.0,
            }
        ],
        output="screen",
        emulate_tty=True,
    )

    return LaunchDescription(
        [
            # Declare args
            DeclareLaunchArgument("drone_id", default_value="1"),
            DeclareLaunchArgument("drone_namespace", default_value="/Drone1"),
            DeclareLaunchArgument("fcu_url", default_value="udp://:14540@localhost:18570"),
            DeclareLaunchArgument("gcs_url", default_value="udp://:@localhost:14550"),
            DeclareLaunchArgument("tgt_system", default_value="1"),
            DeclareLaunchArgument(
                "mission_file",
                default_value="/workspace/aerial_ws/missions/crane_inspection.yaml",
            ),
            SetEnvironmentVariable("DRONE_ID", drone_id),
            # Nodes
            mavros_node,
            autopilot_node,
            offboard_node,
            state_sharing_node,
            traffic_client_node,
            mission_node,
            inference_node,
        ]
    )

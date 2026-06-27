import os
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "ros2_ws" / "src"
AAS = REPO / "external" / "aerial-autonomy-stack"


AIRCRAFT_PACKAGES = {
    "autopilot_interface",
    "autopilot_interface_msgs",
    "drone_traffic_client",
    "imu_publisher",
    "mission",
    "offboard_control",
    "state_sharing",
    "yolo_py",
}

GROUND_PACKAGES = {
    "drone_traffic_controller",
    "ground_system",
    "ground_system_msgs",
}


class AASUnificationContract(unittest.TestCase):
    def test_aas_owned_packages_resolve_from_external_checkout(self):
        for package in sorted(AIRCRAFT_PACKAGES):
            with self.subTest(package=package):
                workspace_entry = SRC / package
                expected_target = AAS / "aircraft" / "aircraft_ws" / "src" / package

                self.assertTrue(workspace_entry.is_symlink(), f"{workspace_entry} must be a link")
                self.assertEqual(expected_target.resolve(), workspace_entry.resolve())
                self.assertTrue(expected_target.exists(), f"{expected_target} must exist")

        for package in sorted(GROUND_PACKAGES):
            with self.subTest(package=package):
                workspace_entry = SRC / package
                expected_target = AAS / "ground" / "ground_ws" / "src" / package

                self.assertTrue(workspace_entry.is_symlink(), f"{workspace_entry} must be a link")
                self.assertEqual(expected_target.resolve(), workspace_entry.resolve())
                self.assertTrue(expected_target.exists(), f"{expected_target} must exist")

    def test_repo_keeps_isaac_sim_60_as_simulation_runtime(self):
        compose = (REPO / "docker-compose.yml").read_text()
        env_example = (REPO / ".env.example").read_text()

        self.assertIn("nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION:-6.0.0}", compose)
        self.assertIn("ISAAC_SIM_VERSION=6.0.0", env_example)
        self.assertNotIn("simulation-image", compose)
        self.assertEqual("22", os.environ.get("ROS_DOMAIN_ID", "22"))

    def test_drone_bringup_uses_aas_control_chain(self):
        launch = (SRC / "pegasus_bringup" / "launch" / "drone_stack.launch.py").read_text()

        self.assertIn('package="autopilot_interface"', launch)
        self.assertIn('executable="px4_interface"', launch)
        self.assertIn('package="offboard_control"', launch)
        self.assertIn('executable="px4_offboard"', launch)
        self.assertIn('package="drone_traffic_client"', launch)
        self.assertIn('package="mission"', launch)
        self.assertIn('package="pegasus_ai"', launch)
        self.assertNotIn('executable="mission_executor"', launch)


if __name__ == "__main__":
    unittest.main()

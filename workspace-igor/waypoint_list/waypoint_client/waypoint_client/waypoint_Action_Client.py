import os, math, yaml
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Quaternion
from std_msgs.msg import String, Bool
from waypoint_action.action import WaypointSet
from aruco_msg.msg import ArucoDocking
from rclpy.action import ActionClient
from ament_index_python.packages import get_package_share_directory

class waypointActionClient (Node):
    def __init__(self):
        super().__init__("waypoint_action_client")
        self.yaw = 0.0
        self.waypoint_queue = []
        self.done_pub = self.create_publisher(Bool, "/waypoint_done", 10)
        self.docking_pub = self.create_publisher(ArucoDocking, "/cmd_aruco_docking", 10)
        self._action_client = ActionClient(
            self, 
            WaypointSet, 
            "waypoint",
            )
        self.command_file = self.create_subscription(
            String,
            "waypoint_filename",
            self.load_file,
            10
        )

    def load_file(self, msg):
        pkg_share_dir = get_package_share_directory('waypoint_client')
        path_name = os.path.join(pkg_share_dir, 'point', msg.data)

        self.get_logger().info(f"Loading waypoints from file: {path_name}")
        if not os.path.isfile(path_name):
            self.get_logger().error(f"File {path_name} does not exist.")
            return
        
        with open(path_name, "r") as f:
            data = yaml.safe_load(f)

        self.waypoint_queue = data.get("waypoints", [])
        self.send_next_waypoint()

    def send_next_waypoint(self):
        if not self.waypoint_queue:
            self.get_logger().info("All waypoints have been completed!")
            done_msg = Bool()
            done_msg.data = True
            self.done_pub.publish(done_msg)
            return
        
        wp = self.waypoint_queue.pop(0)

        if "aruco_docking" in wp:
            docking = wp["aruco_docking"]
            msg = ArucoDocking()
            msg.id = int(docking["id"])
            msg.offset_z = float(docking["offset_z"])
            self.docking_pub.publish(msg)
            self.get_logger().info(f"Published aruco_docking: id={msg.id}, offset_z={msg.offset_z}")
            self.send_next_waypoint()
            return

        x = float(wp["x"])
        y = float(wp["y"])
        yaw = float(wp["yaw"])
        ds = float(wp["duration"])
        
        self.get_logger().info(f"Sending next waypoint: x={x}, y={y}, yaw={yaw}, duration={ds}")
        self.send_goal(x, y, yaw, ds)
    
    def send_goal(self, absis, ordinat, yaw, duration):
        goal_msg = WaypointSet.Goal()
        goal_msg.absis = absis
        goal_msg.ordinat = ordinat
        goal_msg.yaw = yaw
        goal_msg.duration = duration
        self.yaw = yaw
        self._action_client.wait_for_server()

        self._send_goal_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

        return self._send_goal_future

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        if self.yaw == 0.0:
            self.get_logger().info(
                f"Feedback: ({feedback.absis_feedback:.2f}, {feedback.ordinat_feedback:.2f}) progress={feedback.progress}"
            )
        else:
            self.get_logger().info(
                f"Feedback: yaw_feedback={feedback.yaw_feedback:.2f} progress={feedback.progress}"
            )

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info("Goal rejected :(")
            self.waypoint_queue.clear()
            return

        self.get_logger().info("Goal accepted :)")

        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)
    
    def get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f"Result: success={result.success}, message={result.message}")
        
        if result.success:
            self.send_next_waypoint()
        else:
            self.get_logger().error("Waypoint execution failed. Aborting the remaining queue.")
            self.waypoint_queue.clear()

def main(args=None):
    rclpy.init(args=args)

    node = waypointActionClient()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
    
        
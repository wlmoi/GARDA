import os, math
import sys
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class waypointCommand(Node):
    def __init__(self):
        super().__init__("waypoint_action_client")
        self.command_publisher = self.create_publisher(
            String, 
            "waypoint_command", 
            10
            )
        self.filename = ""
    
    def load_file(self, namefile):
        with open(namefile, "r") as f:
            self.filename = f.read()

    def publish_command(self, command):
        msg = String()
        msg.data = command
        self.command_publisher.publish(msg)
        self.get_logger().info(f"Published command: {command}")
def main():
    rclpy.init()
    command = waypointCommand()
    
    path_name = sys.argv[1]
    command.load_file(path_name)
    command.publish_command(command.filename)
    rclpy.shutdown()


if __name__ == "__main__":
    main()

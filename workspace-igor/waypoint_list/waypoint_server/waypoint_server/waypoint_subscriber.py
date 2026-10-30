import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class WaypointSubscriber(Node):
    def __init__(self):
        super().__init__('waypoint_subscriber')
        self.subscription = self.create_subscription(
            Twist,
            'cmd_vel',
            self.waypoint_sub_callback,
            10
        )
        
        self.get_logger().info('dah mulai nih bg wkkwwk')
    def waypoint_sub_callback(self, msg):
        if msg.angular.z == 0.0:
            self.get_logger().info(f'bergerak linier dengan kecepataan-x: {float(msg.linear.x):.2f} dan kecepatan-y:{float(msg.linear.y):.2f}')
        else:
            self.get_logger().info(f'bergerak angular dengan kecepataan: {float(msg.angular.z):.2f}')

def main(args=None):
    rclpy.init(args=args)
    node = WaypointSubscriber()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
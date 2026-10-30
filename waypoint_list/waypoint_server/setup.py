import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='setuptools')

from glob import glob
from setuptools import find_packages, setup
import os

package_name = 'waypoint_server'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/waypoint_server_launch.py']),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
    ],
    
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='majiidkun',
    maintainer_email='muhammadnurmajiid22@gmail.com',
    description='TODO: Package description',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'waypoint_server_node = waypoint_server.waypoint_Action_Server:main',
            'waypoint_subscriber_node = waypoint_server.waypoint_subscriber:main',
            'motion_node = waypoint_server.motion_node:main',
        ],
    },
)

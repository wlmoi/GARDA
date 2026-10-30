import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='setuptools')

from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'waypoint_client'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'point'), glob('point/*')),
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
            'waypoint_client_node = waypoint_client.waypoint_Action_Client:main',
            'waypoint_command_node = waypoint_client.waypoint_command:main',
        ],
    },
)

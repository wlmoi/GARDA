from setuptools import setup, find_packages

package_name = 'igor_controller'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'numpy', 'pyserial'],
    zip_safe=True,
    maintainer='Karol',
    maintainer_email='karol@todo.todo',
    description='ROS 2 Controller Node, Heading Estimator, and Hardware Bridges for Hiwonder JetAuto AMR.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'controller_node = igor_controller.controller_node:main',
        ],
    },
)

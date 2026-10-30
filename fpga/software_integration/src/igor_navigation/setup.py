from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'igor_navigation'

# Collect all files in weights directory recursively for package data / data_files
weights_files = []
for root, dirs, files in os.walk(os.path.join(package_name, 'weights')):
    for f in files:
        rel_path = os.path.relpath(os.path.join(root, f), package_name)
        weights_files.append(rel_path)

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    package_data={
        package_name: weights_files,
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'numpy'],
    zip_safe=True,
    maintainer='Karol',
    maintainer_email='karol@todo.todo',
    description='IGOR Navigation Algorithms Package containing 5 obstacle avoidance controllers and weights.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'retrain_ai = igor_navigation.retrain_ai:main',
        ],
    },
)

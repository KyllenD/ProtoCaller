from setuptools import find_packages, setup


setup(
    name='ProtoCaller',
    version='0.0.1',
    author='',
    author_email='',
    description='',
    long_description='',
    long_description_content_type='text/markdown',
    url='https://github.com/kyllend/protocaller',
    license='MIT',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ],
    keywords=[
        'chemistry',
        'electrostatic potential',
        'shape',
        'similarity',
        'RDKit'
    ],
    include_package_data=True,
    package_data={'': ['QM_137k.pt']},
)

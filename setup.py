from setuptools import setup, find_packages

def get_requirements_from_file(filepath):
    requires = []
    with open(filepath, 'r') as f:
        requires.append(f.readline())
    return requires

setup(
    name='coinbitrage',
    version='0.1',
    packages=find_packages(),
    install_requires=get_requirements_from_file('requirements.txt'),
    entry_points='''
        [console_scripts]
        coin=scripts:coin
    '''
)

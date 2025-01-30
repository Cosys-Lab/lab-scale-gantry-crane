from setuptools import setup, find_packages

setup(
    name="gantrylib",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "scipy",
        "numpy",
        "pyyaml",
        "rockit-meco",
        "pytrinamic",
        "psycopg[binary]",
        "typing-extensions"
    ], 
)

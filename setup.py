from setuptools import setup, find_packages

setup(
    name="watch_tower",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "boto3>=1.26.0",
        "python-dotenv>=1.0.0",
        "pytest>=7.0.0",
        "pytest-mock>=3.10.0",
        "click>=8.0.0",
        "tenacity>=8.0.0"
    ],
    entry_points={
        'console_scripts': [
            'watch-tower=cli:cli',
        ],
    },
    python_requires='>=3.8',
) 
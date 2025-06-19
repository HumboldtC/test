from setuptools import setup, find_packages

setup(
    name="wiki-content-risk-analyzer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.3",
        "flask>=2.0.0",
        "numpy>=1.19.0",
    ],
    entry_points={
        'console_scripts': [
            'risk-analyzer=src.main:main',
        ],
    },
    author="AI Risk Pattern Team",
    author_email="example@example.com",
    description="多轮对话中的内容风险检测工具",
    keywords="content risk, conversation analysis, pattern detection",
    python_requires=">=3.6",
)
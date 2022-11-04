from setuptools import setup, find_packages
import pathlib

WORK_DIR = pathlib.Path(__file__).parent

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

__version__ = ""
exec(open('efb_wechat_comwechat_slave/__version__.py').read())


setup(
    name="efb-wechat-comwechat-slave",
    version=__version__,
    description='EFB Slave for WeChat on ComWeChat',
    author='honus',
    author_email="honusmr@gmail.com",
    url="https://github.com/0honus0/efb-wechat-comwechat-slave",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    python_requires='>=3.7',
    keywords=["wechat", ],
    install_requires=[
        "wechatrobot",
        "ehforwarderbot",
        "PyYaml>=5.3",
        "cachetools",
        "requests",
        "python-magic",
        "lxml",
        "pilk",
        "pydub",
        "lottie",
        "cairosvg",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: User Interfaces',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        "Operating System :: OS Independent"
    ],
    entry_points={
        'ehforwarderbot.slave': 'honus.comwechat = efb_wechat_comwechat_slave:ComWeChatChannel',
    }
)

# seleniumonitor

## Introduction
Website change detection monitoring based on selenium

## Notification Support
- Mail
- Line Notify

## Requirements
- mail command on Linux
    - ```sudo apt-get install mailutils```
- Line Notify token
    - [Line Notify](https://notify-bot.line.me/)
- Chrome Driver
    - [Chrome Driver](https://chromedriver.chromium.org/)
- packages
    - ```pip3 install -r requirements.txt```

## Configuration
- .env
    - rename .env.example to .env and set variable properly

## Run
- ```python3 main.py```

## Reference
- [changedetection.io](https://github.com/dgtlmoon/changedetection.io)
    - Notice that frontend, [templates](./templates) and [static](./static) are copy word for word from this repo
    - Others part are written by myself

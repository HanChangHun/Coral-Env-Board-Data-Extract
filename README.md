# Coral-Env-Board-Data-Extract

1. **패키지 저장소 추가 및 패키지 설치**

```bash
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
echo "deb https://packages.cloud.google.com/apt coral-cloud-stable main" | sudo tee /etc/apt/sources.list.d/coral-cloud.list

curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

sudo apt update

sudo apt upgrade

sudo apt install python3-coral-enviro
```

만약 에러가 발생하면 다음 사이트들을 참고하세요:
- [GitHub Issue 95](https://github.com/f0cal/google-coral/issues/95)

그리고 에러가 계속 발생하여 진행이 어려울 경우 다음 명령어를 실행하세요:
```bash
sudo apt-get install --reinstall python3-coral-enviro
sudo apt-get install --reinstall coral-enviro-drivers-dkms
```

개인적으로, 다음 명령어를 수행한 후 문제가 해결되었습니다:
```bash
sudo apt-get install --reinstall raspberrypi-kernel-headers
```

2. **서비스 파일 생성 및 설정**

`/etc/systemd/system/enviro_board.service` 파일을 생성하여 아래 내용을 입력합니다:
```ini
[Unit]
Description=My Enviro Script
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/workspaces/Coral-Env-Board-Data-Extract/my_enviro.py --rotate
WorkingDirectory=/home/pi/workspaces/Coral-Env-Board-Data-Extract
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

3. **서비스 시작 및 활성화**

다음 명령어를 실행하여 서비스를 리로드하고, 시작하고, 부팅 시 자동으로 시작되도록 활성화합니다:
```bash
sudo systemctl daemon-reload
sudo systemctl start enviro_board.service
sudo systemctl enable enviro_board.service
```

이렇게 하면 Coral-Env-Board-Data-Extract 설정이 완료됩니다.
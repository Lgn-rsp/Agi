# LOGOS lite-peer

Минимальный federated peer для участия в LOGOS-сети без полного 99% CPU
brain.cycle. Запускается через systemd на UK/NL VPS (или любом ≥2GB RAM).

## Запуск

```
sudo bash install_remote_peer.sh \
    --name philosophy \
    --port 8765 \
    --bootstrap "main=http://45.12.133.125:8765"
```

После установки:

```
systemctl status logos-lite-peer.service
journalctl -u logos-lite-peer -f
```

## Env vars управления

| var | default | что делает |
|---|---|---|
| `LOGOS_LITE_MODE` | `1` | skip O(N²) analog_cycle, slower main loop |
| `LOGOS_PEER_NETWORK` | `1` | enable HTTP gossip on this peer |
| `LOGOS_PEER_PORT` | `8765` | HTTP listener port |
| `LOGOS_PEER_NAME` | `<from --name>` | unique peer identifier |
| `LOGOS_PEER_URL` | auto | `http://<this-host-ip>:<port>` |
| `LOGOS_PEER_BOOTSTRAP` | (empty) | `name1=url1,name2=url2` |


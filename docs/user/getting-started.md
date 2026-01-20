![Started](../images/rocket.png){ align=right width="90" }

# Getting Started with Mixtape Society

Welcome to Mixtape Society! Whether you're setting up your own server to create and share mixtapes, or you've received a mixtape link from a friend, we've got you covered.

---

## 🎯 Choose Your Path

### 🎨 I Want to Create Mixtapes

You want to run your own Mixtape Society server to craft and share mixtapes from your music library.

**[→ Creator's Guide](creators/index.md)**

**What you'll learn:**

- Installing and setting up your server
- Creating your first mixtape
- Managing your music collection
- Sharing mixtapes with friends
- Privacy and access control

**Perfect for:**

- Music enthusiasts with personal music libraries
- People who love curating playlists for friends
- Anyone wanting to run their own music sharing server

---

### 🎧 I Received a Mixtape

Someone shared a mixtape link with you and you want to know how to listen to it.

**[→ Recipient's Guide](recipients/index.md)**

**What you'll learn:**

- Opening and playing mixtapes
- Using player controls and features
- Streaming to TVs and speakers
- Adjusting quality settings
- Mobile and desktop tips

**Perfect for:**

- Friends and family receiving mixtape links
- Anyone who got a QR code or gift link
- People wanting to cast to Chromecast or AirPlay

---

## 🚀 Quick Start (For Creators)

If you just want to get a server running immediately:

```bash
docker run -d \
  --name mixtape-society \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music:ro \
  -v /data/mixtape-society:/app/collection-data \
  -e APP_PASSWORD=YourStrongPassword123! \
  ghcr.io/mark-me/mixtape-society:latest
```

→ Open [http://localhost:5000](http://localhost:5000), log in, and start creating!

[Full installation guide →](creators/installation.md)

---

## 💡 Not Sure Which Path?

**You're a Creator if:**

- You have a music library you want to share
- You want to run your own server
- You need login/admin access
- You're setting up Mixtape Society

**You're a Recipient if:**

- Someone sent you a mixtape link
- You just want to listen to music
- You don't need to create mixtapes
- You're using someone else's server

---

## 🆘 Need Help?

- **Creators:** Check the [Creator FAQ](creators/faq.md)
- **Recipients:** Check the [Recipient FAQ](recipients/faq.md)
- **Everyone:** Visit our [GitHub Issues](https://github.com/mark-me/mixtape-society/issues)

---

Enjoy the mixtape magic! 🚀

# Project Backlog

> Ideas and features to implement later. Move items to GitHub Issues when ready to work on them.

---

## Telemetry & Tracking

### Setup Telemetry (Priority: Medium)

**Problem**: We want to track adoption (how many people use the starter, what features are popular) without requiring everyone to push branches.

**Options Explored**:

1. **Elastic Telemetry** (dogfooding) - Send anonymous events to a shared ES index
   - Pros: Rich analytics, dashboards, dogfooding
   - Cons: Requires maintaining a shared ES deployment
   
2. **Simple Webhook** - POST to a serverless function
   - Pros: Lightweight
   - Cons: Still needs infrastructure
   
3. **GitHub Discussions** - Auto-create a "Demo Registry" discussion on setup
   - Pros: Zero infrastructure, visible to team, searchable
   - Cons: Requires `gh` auth, no rich analytics

**Recommendation**: Start with Option 3 (GitHub Discussions), upgrade to Option 1 if we need better analytics.

**Implementation sketch**:
```python
# In interactive_setup.py, after successful setup
def register_demo(demo_name: str, features: list, username: str = None):
    subprocess.run([
        "gh", "discussion", "create",
        "--repo", "elastic/elastic-demo-starter",
        "--category", "Demo Registry",
        "--title", f"Demo: {demo_name}",
        "--body", f"Features: {', '.join(features)}\nCreated: {date}"
    ])
```

**Data to collect** (anonymous):
- Timestamp
- Demo types selected (search, chat, analytics, etc.)
- Platform (macOS, Linux, Windows)
- Success/failure

**Data NOT to collect**:
- Usernames, emails, IPs
- Customer names
- Credentials, file paths

---

## Future Ideas

### Visual Demo Builder
- Low-code interface for configuring demos
- Select features, branding, deployment target via UI
- Generate customised starter

### Demo Gallery
- Showcase of completed demos (screenshots, descriptions)
- Inspiration for new demo builders
- Could live in GitHub Wiki or separate site

### One-Click Deploy Templates
- Pre-configured Cloud Run deploy buttons
- "Deploy to GCP" badge in README

---

*Add new ideas below. Date and initial them.*

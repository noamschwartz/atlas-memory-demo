> **DEPRECATED** - This file is kept as a reference only.
>
> The onboarding flow is now: `./setup.sh` then start a new AI session.
> AI assistants use `docs/prompts/WELCOME_PROMPT.md` (loaded automatically by CLAUDE.md).

# Onboarding Reference (Legacy)

The procedural checklist that used to live here has been replaced by a consultative brainstorm flow. See `docs/prompts/WELCOME_PROMPT.md` for the current entry point.

The sections below are preserved as standalone reference material.

---

## Creating an API Key (for Agent Builder)

If you need to create an API key:

1. **Navigate to API Keys**: Kibana -> Stack Management -> Security -> API Keys

2. **Click "Create API Key"**

3. **Configure permissions** - At minimum, you need:

   ```json
   {
     "agent_builder": {
       "application": "kibana-.kibana",
       "privileges": ["feature_agentBuilder.all"],
       "resources": ["*"]
     }
   }
   ```

   Or simply use a key with `superuser` role for demos.

4. **Copy the encoded key** (the Base64 string, not the ID)

5. **Save it** - You won't be able to see it again!

**Common API Key Errors:**

| Error              | Cause                          | Fix                                                            |
| ------------------ | ------------------------------ | -------------------------------------------------------------- |
| HTTP 401           | Invalid or expired API key     | Create a new API key                                           |
| HTTP 403           | Key lacks required permissions | Create key with `agent_builder` privileges                     |
| HTTP 404           | Agent not found                | Check AGENT_ID is correct                                      |
| Connection refused | Wrong Kibana URL               | Verify URL starts with `https://` and ends with correct domain |

---

## Configuring Search Fields

The search page (`/search`) works out-of-the-box with robust defaults, but displays raw JSON if the index fields don't match the expected product structure.

### Discover available fields

```bash
curl http://localhost:8001/api/search/fields | jq
```

### Update frontend configuration

Edit `frontend/src/config/searchConfig.ts` — map your index fields to the display config:

- `title`: Field containing the main title/name
- `description`: Field containing description text
- `image`: Field containing image URL
- `price`: Field containing price (numeric)
- `brand`: Field for brand/manufacturer
- `category`: Field for category/type

### Troubleshooting Search

| Issue                         | Cause                                             | Fix                                                      |
| ----------------------------- | ------------------------------------------------- | -------------------------------------------------------- |
| "Elasticsearch not connected" | Backend can't reach ES                            | Check `ELASTIC_CLOUD_ID` and `ELASTIC_API_KEY` in `.env` |
| Results show but no facets    | Facet fields don't exist or aren't `keyword` type | Check field types in mapping, use `.keyword` subfield    |
| Images not loading            | Wrong field name or URLs are relative             | Verify `display.image` points to field with full URLs    |
| "No results" for all queries  | Index is empty or field names wrong               | Check index has documents, verify search field names     |

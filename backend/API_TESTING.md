# End-to-End API Testing Through Swagger

## Prerequisites

Start the database services:

```powershell
cd E:\Srikanth\Srikanth\Learning\Dynamic_Forms\db
docker compose up -d
```

Start the backend from the `backend` folder:

```powershell
cd E:\Srikanth\Srikanth\Learning\Dynamic_Forms\backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Uvicorn automatically restarts the backend when Python files under `backend/app` change.

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

For each endpoint below, expand it, click **Try it out**, enter the request values, and click **Execute**.

## Swagger JSON Payload Quick Reference

Use these JSON bodies directly in Swagger's **Request body** editor.

### Generate a field

```json
{
  "session_id": "test-session-001",
  "prompt": "Create a required full name text field with a maximum length of 100 characters"
}
```

### Refine the same field

Use the same `session_id` as the generate request:

```json
{
  "session_id": "test-session-001",
  "prompt": "Change the label to Customer Full Name and add an email validation rule"
}
```

### Publish the field

Publishing is independent of the generation session. Copy the final values from the draft response and submit the complete template:

```json
{
  "name": "customer_full_name_test",
  "label": "Customer Full Name",
  "field_type": "text",
  "angular_config": {
    "angular_tag": "mat-form-field",
    "inner_element": "input matInput"
  },
  "validation_rules": {
    "required": true,
    "maxlength": 100,
    "email": true
  },
  "api_config": null
}
```

### Build a form layout

```json
{
  "session_id": "form-session-001",
  "prompt": "Build a customer registration form using the available full name field"
}
```

### Create a persisted form definition

Endpoint: `POST /api/forms/definitions`

```json
{
  "title": "Customer Registration",
  "description": "Customer onboarding form"
}
```

Copy the returned `id` for `POST /api/forms/{form_id}/versions`.

Reuse `form-session-001` for later form changes. For example:

```json
{
  "session_id": "form-session-001",
  "prompt": "Add an email field after the full name field and make both fields span 6 columns"
}
```

### Override an existing field definition

First call `GET /api/fields/` and copy the `id` of the field to override. Replace `FIELD-ID-HERE` in the endpoint path:

Endpoint: `PUT /api/fields/FIELD-ID-HERE`

Use this request body for the first prompt:

```json
{
  "name": "full_name",
  "label": "Full Name",
  "field_type": "text",
  "angular_config": {
    "angular_tag": "mat-form-field",
    "inner_element": "input matInput"
  },
  "validation_rules": {
    "required": true,
    "maxlength": 200
  },
  "api_config": null
}
```

The endpoint updates the existing database row and returns the updated field template. It returns `404` when the ID does not exist and `409` if the replacement name is already used by another field.

### Delete a field definition

Endpoint: `DELETE /api/fields/FIELD-ID-HERE`

Replace `FIELD-ID-HERE` with the field `id` returned from `GET /api/fields/`.

No request body is required.

Expected response:

```json
{
  "status": "deleted",
  "field_id": "..."
}
```

The endpoint returns `404` when the field does not exist.

### Save a form version

Replace `PASTE-PUBLISHED-FIELD-ID-HERE` with the `id` returned from `POST /api/fields/publish`:

```json
{
  "version_number": "1.0.0",
  "layout_tree": [
    {
      "field_id": "PASTE-PUBLISHED-FIELD-ID-HERE",
      "order": 0,
      "column_span": 12
    }
  ]
}
```

### List published forms

Endpoint: `GET /api/forms/published`

No request body is required. This returns all published form versions, including their form metadata and `layout_tree`.

### List published versions for one form

Endpoint: `GET /api/forms/{form_id}/published`

Replace `{form_id}` with the form definition ID, for example:

```text
GET /api/forms/c2ea203d-8fef-4d83-a858-0ce7da37dc3f/published
```

No request body is required.

### Manage form definitions

Create a form definition:

```text
POST /api/forms/definitions
```

```json
{
  "title": "Customer Registration",
  "description": "Customer onboarding form"
}
```

List definitions:

```text
GET /api/forms/definitions
```

Get one definition:

```text
GET /api/forms/definitions/{form_id}
```

Update one definition:

```text
PUT /api/forms/definitions/{form_id}
```

```json
{
  "title": "Updated Customer Registration",
  "description": "Updated onboarding form"
}
```

### List form versions

All versions for one form:

```text
GET /api/forms/{form_id}/versions
```

One version:

```text
GET /api/forms/{form_id}/versions/{version_id}
```

These responses include the version status (`draft` or `published`) and `layout_tree`.

### Submit a published form

Endpoint: `POST /api/forms/{form_id}/submissions`

Use a published `version_id`:

```json
{
  "version_id": "PUBLISHED-VERSION-ID-HERE",
  "submission_data": {
    "fullName": "Jane Doe",
    "email": "jane@example.com"
  }
}
```

List submissions:

```text
GET /api/forms/{form_id}/submissions
```

Get one submission:

```text
GET /api/forms/{form_id}/submissions/{submission_id}
```

The following endpoints do not require a JSON body:

- `GET /health`
- `POST /api/spec/refresh`
- `GET /api/fields/`
- `GET /api/forms/published`
- `GET /api/forms/{form_id}/published`
- `GET /api/forms/definitions`
- `GET /api/forms/definitions/{form_id}`
- `GET /api/forms/{form_id}/versions`
- `GET /api/forms/{form_id}/versions/{version_id}`
- `GET /api/forms/{form_id}/submissions`
- `GET /api/forms/{form_id}/submissions/{submission_id}`
- `POST /api/forms/{form_id}/versions/{version_id}/publish`

## 1. Check the backend

Endpoint: `GET /health`

No request body is required.

Expected response:

```json
{
  "status": "ok"
}
```

## 2. Refresh the local vector database

Endpoint: `POST /api/spec/refresh`

No request body is required. Click **Try it out**, then **Execute**.

Expected response:

```json
{
  "status": "success",
  "documents_indexed": 4
}
```

The document count depends on the number of supported fields in `app/data/angular_material_capabilities.json`. The first refresh may download the local embedding model.

### Refresh published field and form indexes

The application keeps separate Chroma collections for:

- Angular Material capabilities: `angular_material_spec`
- Published field templates: `published_fields`
- Published form versions: `published_forms`

PostgreSQL remains the source of truth. Use these endpoints to rebuild the semantic indexes:

```text
POST /api/spec/refresh-fields-index
POST /api/spec/refresh-forms-index
POST /api/spec/refresh-all-indexes
```

The first endpoint indexes all rows from `field_templates`. The second indexes published form versions and their embedded field snapshots. The third rebuilds all three collections and returns document counts.

## 3. Regenerate capabilities from official Angular Material documentation

Endpoint: `POST /api/spec/generate-capabilities`

This fetches the allowlisted official Angular Material documentation pages, uses the configured LLM to normalize their component metadata, validates the result, writes `app/data/angular_material_capabilities.json`, and refreshes Chroma.

Use this request body to regenerate all currently supported components:

```json
{
  "components": ["text", "autocomplete", "select", "checkbox"]
}
```

The endpoint does not accept arbitrary URLs or component names. The generated file is replaced only after validation succeeds.

## 4. Generate a field draft

Endpoint: `POST /api/fields/generate`

Use this request body:

```json
{
  "session_id": "test-session-001",
  "prompt": "Create a required full name text field with a maximum length of 100 characters"
}
```

Copy the returned draft and confirm that it contains `field_type`, `label`, `angular_config`, and `validation_rules`.

The generate response is intentionally identical to the publish request body. Copy the complete response JSON into `POST /api/fields/publish` without adding or removing fields.

## 4. Refine the field draft

Call `POST /api/fields/generate` again. Keep the exact same `session_id` and change only the prompt:

```json
{
  "session_id": "test-session-001",
  "prompt": "Change the label to Customer Full Name and add an email validation rule"
}
```

The response should reflect the previous draft and the requested changes. A different `session_id` starts a new conversation.

## 5. Publish the field template

Endpoint: `POST /api/fields/publish`

Use the complete final template body from the generate response. You may change the `name` or any other field before publishing. `session_id` is not required:

```json
{
  "name": "customer_full_name_test",
  "label": "Customer Full Name",
  "field_type": "text",
  "angular_config": {
    "angular_tag": "mat-form-field",
    "inner_element": "input matInput"
  },
  "validation_rules": {
    "required": true,
    "maxlength": 100,
    "email": true
  },
  "api_config": null
}
```

Copy the `id` from the response. This is the published field template ID needed by later form requests.

## 6. List published field templates

Endpoint: `GET /api/fields/`

No request body is required. Confirm that `customer_full_name_test` appears in the response.

## 7. Build a form layout

Endpoint: `POST /api/forms/build`

Use this request body:

```json
{
  "session_id": "form-session-001",
  "prompt": "Build a customer registration form using the available full name field"
}
```

The response contains the complete form JSON. Each layout item includes the complete `field` definition loaded from the `field_templates` table using `field_id`:

```json
{
  "session_id": "form-session-001",
  "form_definition": {
    "title": "Customer Registration",
    "description": "Customer onboarding form",
    "layout_tree": [
      {
        "field_id": "PUBLISHED-FIELD-ID",
        "order": 0,
        "column_span": 12,
        "field": {
          "id": "PUBLISHED-FIELD-ID",
          "name": "fullName",
          "label": "Full Name",
          "field_type": "text",
          "angular_config": {
            "angular_tag": "mat-form-field",
            "inner_element": "input matInput"
          },
          "validation_rules": {
            "required": true,
            "maxlength": 200
          },
          "api_config": null
        }
      }
    ]
  }
}
```

Refine it by calling the same endpoint with the same session ID and only a new prompt:

```json
{
  "session_id": "form-session-001",
  "prompt": "Add an email field after the full name field and make both fields span 6 columns"
}
```

Every response contains the latest complete form JSON.

## 8. Create a form definition

Use `POST /api/forms/definitions` to create the form definition and copy the returned `id`. This UUID is used when saving the generated form as a version.

## 9. Save a form version

Endpoint: `POST /api/forms/{form_id}/versions`

Replace `{form_id}` in Swagger with the UUID returned from `POST /api/forms/definitions`.

Use this request body, replacing the example `field_id` with the published field ID from step 5:

```json
{
  "version_number": "1.0.0",
  "layout_tree": [
    {
      "field_id": "PASTE-PUBLISHED-FIELD-ID-HERE",
      "order": 0,
      "column_span": 12
    }
  ]
}
```

Copy the returned `version_id`.

Alternatively, save the previous complete form JSON directly without using a session:

Endpoint: `POST /api/forms/{form_id}/versions/from-definition`

Use the form definition ID and paste the full response from `POST /api/forms/build` into the body. Add `version_number`:

```json
{
  "version_number": "1.0.0",
  "form_definition": {
    "title": "Customer Registration",
    "description": "Customer onboarding form",
    "layout_tree": [
      {
        "field_id": "PASTE-PUBLISHED-FIELD-ID-HERE",
        "order": 0,
        "column_span": 12
      }
    ]
  }
}
```

The endpoint does not use a session. If you paste a previous build response containing `session_id`, it is ignored automatically. This saves `form_definition.layout_tree` as a draft version.

### Edit the same draft version

Use this endpoint to replace a draft repeatedly before publishing:

Endpoint: `PUT /api/forms/{form_id}/versions/{version_number}/draft`

Example:

```text
PUT /api/forms/c2ea203d-8fef-4d83-a858-0ce7da37dc3f/versions/1.0.1/draft
```

Request body:

```json
{
  "form_definition": {
    "title": "Customer Registration",
    "description": "Updated customer onboarding form",
    "layout_tree": [
      {
        "field_id": "05edc8c4-b5c5-4889-a9c2-fdbaa44a29ea",
        "order": 0,
        "column_span": 6
      },
      {
        "field_id": "d7adf754-6202-4c30-9b15-860e4e2a1493",
        "order": 1,
        "column_span": 6
      }
    ]
  }
}
```

Call this endpoint as many times as needed with the same form ID and version number. It returns `409` after that version has been published.

## 10. Publish the form version

Endpoint: `POST /api/forms/{form_id}/versions/{version_id}/publish`

Replace both path values:

- `{form_id}`: the form definition UUID from step 8
- `{version_id}`: the version ID from step 9

No request body is required.

Expected response:

```json
{
  "status": "published",
  "version_id": "..."
}
```

## 11. Test the lookup endpoint

Endpoint: `GET /api/proxy/lookup`

Click **Try it out** and enter this query parameter:

```text
q=uni
```

Expected response:

```json
[
  "United States",
  "United Kingdom"
]
```

## Recommended test order

1. `GET /health`
2. `POST /api/spec/refresh`
3. `POST /api/fields/generate`
4. `POST /api/fields/generate` again with the same session ID
5. `POST /api/fields/publish`
6. `GET /api/fields/`
7. `PUT /api/fields/{field_id}`
8. `POST /api/forms/build`
8. `POST /api/forms/definitions`
9. `POST /api/forms/build` repeatedly with the same session ID
10. `POST /api/forms/{form_id}/versions/from-definition` or `POST /api/forms/{form_id}/versions`
11. `POST /api/forms/{form_id}/versions/{version_id}/publish`
12. `GET /api/forms/published`
13. `GET /api/forms/{form_id}/published`
14. `GET /api/proxy/lookup`

The most important checks are that field refinement remembers the session history, the vector refresh reports a successful document count, and the Form Builder Agent selects only published field IDs.

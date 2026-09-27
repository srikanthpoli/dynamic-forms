# Dynamic Forms App - PPT Preparation Notes

## Slide 1: Purpose Of The App

### Title
AI-Powered Dynamic Forms For TPS Implementation Requests

### Main Purpose
The purpose of this application is to let business and operations users create, manage, assign, and collect dynamic forms without writing code.

Instead of manually building every form in Angular, the app uses AI agents to generate reusable field templates, assemble complete forms, and support the TPS implementation request workflow.

### Problem It Solves
- Form requirements change often during onboarding and implementation work.
- Developers should not need to manually code every new field or form variation.
- Business users need a faster way to create forms, publish them, assign them to implementation requests, and collect responses.

### What The App Enables
- Generate form fields from natural language prompts.
- Save approved fields into a reusable field library.
- Build complete forms using published field templates.
- Version and publish forms.
- Assign published forms to TPS implementation requests.
- Release forms to clients/users and collect submitted data.

### Speaker Notes
This application acts as an AI-assisted form creation and workflow platform. It reduces manual development effort by allowing users to describe what they need, letting the AI generate structured Angular Material-compatible form definitions, and then using those definitions in a controlled publish-and-release workflow.

## Slide 2: High-Level Architecture

### Flow
User -> Angular Frontend -> FastAPI Backend -> AI Agents + PostgreSQL + Chroma Vector Store

### Components
- Angular frontend: user interface for field building, form building, TPS workflow, and form review.
- FastAPI backend: exposes API endpoints and coordinates database, LangGraph agents, and workflow logic.
- PostgreSQL: stores field templates, form definitions, form versions, TPS IRs, form assignments, submissions, and events.
- Chroma vector store: retrieves Angular Material capabilities and published form versions; client submission answers are not indexed there.
- LLM provider: generates structured field/form responses using Grok or another configured provider.

### Speaker Notes
The frontend does not directly generate form logic by itself. It sends user requests to the backend. The backend calls the correct agent, validates the result, stores the approved data, and returns structured JSON that the Angular app can render dynamically.

## Slide 3: Field Builder Agent

### What It Does
The Field Builder Agent creates a single reusable form field from a natural language prompt.

### Example Prompt
Create a required email field for customer contact information.

### Agent Responsibilities
- Reads the user prompt.
- Searches the Angular Material capability registry from the vector store.
- Generates a valid field template.
- Includes field type, label, Angular Material config, validations, validation messages, and optional API config.
- Supports refinement using conversation history.

### Output Example
- Field name: customer_email
- Field type: text/email
- Label: Customer Email
- Validation: required + email
- Validation message: Please enter a valid email address.

### Speaker Notes
The Field Builder Agent is focused only on creating fields. It does not build full forms. Its job is to produce accurate, reusable field templates that follow the app's Angular Material rendering rules.

## Slide 4: Form Builder Agent

### What It Does
The Form Builder Agent creates a full form layout using already published field templates.

### Important Rule
It does not invent new fields. It only selects fields that already exist in the published field library.

### Agent Responsibilities
- Reads the user's form request.
- Loads available published field templates from PostgreSQL.
- Selects matching fields.
- Arranges fields in a logical order.
- Creates a form title, description, and layout tree.
- Preserves or refines previous layout based on conversation history.

### Example Prompt
Build a customer onboarding form with name, email, country, and tax identification fields.

### Speaker Notes
This separation keeps the workflow controlled. First, users create and approve individual fields. Then the Form Builder Agent arranges those approved fields into complete forms. This prevents the app from publishing forms with unknown or unsupported fields.

## Slide 5: TPS IR Assist Agent

### What It Does
TPS IR Assist helps users ask questions about one TPS implementation request, find suitable published forms, and compare the IR with its latest submitted client form.

### LangGraph Flow
1. Classify the user's request: general IR question, published-form request, assignment, or submission comparison.
2. Retrieve published form candidates only when the request needs them.
3. Load the latest submitted form from PostgreSQL only for comparison requests.
4. Send the relevant IR and retrieved context to the LLM for a natural-language answer.
5. Return an exact published form/version for UI confirmation when the user selects one.

### Form Selection
- Published versions are indexed with their `form_id`, `version_id`, title, and version number.
- Selection is resolved against indexed candidates, not an ID invented by the LLM.
- If multiple versions of a form match and the user did not specify one, the agent asks which version they mean.
- The UI assigns the exact candidate only after the user confirms.

### Submitted-Form Comparison
- The agent loads only the newest submission with status `submitted` for the current IR.
- It passes the IR record and the submission's stored form snapshot and answers to the LLM.
- The LLM compares by meaning, even when form labels and IR column names differ, then explains the findings in plain text in the chat.
- Draft and released-but-unsubmitted forms are excluded. Submitted answers are fetched from PostgreSQL and are not added to the shared Chroma index.

### Important Rule
It must not invent customer facts, submissions, form IDs, or workflow state. It uses DB-loaded IR/submission data and published-form candidates supplied by backend tools. It does not display a generated field-by-field status table.

### Speaker Notes
TPS IR Assist is now a routed LangGraph workflow rather than one undifferentiated chat call. Each request activates only the needed retrieval path. For comparisons, the model receives the full latest submitted form snapshot and IR data and responds conversationally; the backend does not force exact field-name matching.

## Slide 6: How Forms Are Created

### Step-By-Step
1. User describes a required field.
2. Field Builder Agent generates the field template.
3. User reviews and publishes the field.
4. Published fields are saved in PostgreSQL and indexed for search.
5. User asks Form Builder Agent to build a form.
6. Form Builder Agent selects from published fields only.
7. User saves the form as a draft version.
8. User publishes the form version.

### Result
The published form is now available for TPS workflows and client data collection.

### Speaker Notes
The app uses a staged process: generate, review, publish, assemble, version, and publish again. This gives users flexibility while still keeping governance over what becomes available for real workflows.

## Slide 7: How Forms Are Sent Or Released

### Main Idea
Forms are not sent as static files. The app stores the form structure as JSON and releases a published form version to a TPS implementation request.

### Release Flow
1. A TPS implementation request is selected.
2. User searches or chooses a published form.
3. The form is assigned to the implementation request.
4. The app creates a form submission record with a snapshot of the form version.
5. User releases the assigned form.
6. Client or reviewer fills out the dynamic form.
7. Submitted data is saved back to PostgreSQL.
8. Submission events track actions like assigned, released, saved, recalled, and submitted.

### Why Snapshotting Matters
When a form is assigned or submitted, the app stores a snapshot of the form structure. This protects old submissions from future form changes.

### Speaker Notes
The app sends forms by releasing a specific published version into the TPS workflow. The frontend renders the form dynamically from JSON. When the user completes it, only the response data is submitted back, along with its link to the original form snapshot.

## Slide 8: Data Stored In The App

### Main Tables
- field_templates: reusable published fields.
- form_definitions: form metadata such as title and description.
- form_versions: draft and published versions of forms.
- tps_irmain: TPS implementation requests.
- ir_forms: forms assigned to implementation requests.
- form_submissions: self-contained form snapshot and draft/submitted response data. IR Assist reads only the latest `submitted` record for a comparison.
- submission_events: workflow audit history.

### Speaker Notes
The database is designed to separate reusable fields, form definitions, published versions, TPS assignments, and actual submissions. This keeps the app flexible and traceable.

## Slide 9: Benefits

### Business Benefits
- Faster form creation.
- Less dependency on developers for every new form.
- Reusable field library.
- Controlled publish workflow.
- Easier TPS onboarding and implementation request support.

### Technical Benefits
- JSON-based dynamic forms.
- Angular Material-compatible rendering.
- Versioned form publishing.
- PostgreSQL persistence.
- LangGraph intent routing and tool-based retrieval.
- Vector search for published forms/capabilities; private submitted answers stay in PostgreSQL.
- API-driven architecture.

### Speaker Notes
The key value is speed with control. Users can move quickly, but the app still keeps validation, versioning, publishing, and submission tracking structured.

## Slide 10: Closing Summary

### Summary
This application is an AI-assisted dynamic form platform for TPS workflows. It helps users generate fields, build forms, publish versions, assign forms to implementation requests, and collect responses through a structured release and submission process.

### Final Message
The app turns form creation from a manual development task into a guided, reusable, and workflow-ready process.
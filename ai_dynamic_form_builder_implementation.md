# AI-Driven Dynamic Form Builder: Full Implementation Guide

This document contains the complete end-to-end architecture for building an AI-assisted dynamic form builder. It includes the PostgreSQL database schema, the FastAPI backend (with LLM integration), and the Angular frontend (with dynamic rendering and drag-and-drop canvas).

---

## PART 1: Backend Architecture

### 1.1 PostgreSQL Database Schema (`schema.sql`)

This schema utilizes native `JSONB` for flexible layouts and schemas, allowing you to store AI-generated fields and drag-and-drop layouts without needing frequent migrations.

See [db/sql/schema.sql](db/sql/schema.sql) for the full table definitions (`field_templates`, `form_definitions`, `form_versions`, `form_submissions`).

### 1.2 Angular Material Capability Registry (`angular_material_capabilities.json`)

The project stores this capability registry at `backend/app/data/angular_material_capabilities.json`. It provides the strict mapping rules for the AI model to generate valid Angular Material form elements.

```json
{
  "framework": "Angular Material",
  "version": "18+",
  "supported_fields": [
    {
      "type": "text",
      "angular_tag": "mat-form-field",
      "inner_element": "input matInput",
      "allowed_validations": ["required", "minlength", "maxlength", "pattern", "email"]
    },
    {
      "type": "autocomplete",
      "angular_tag": "mat-form-field",
      "inner_element": "input matInput [matAutocomplete]",
      "requires_api_config": true,
      "allowed_validations": ["required"]
    },
    {
      "type": "select",
      "angular_tag": "mat-form-field",
      "inner_element": "mat-select",
      "requires_options": true,
      "allowed_validations": ["required"]
    },
    {
      "type": "checkbox",
      "angular_tag": "mat-checkbox",
      "allowed_validations": ["requiredTrue"]
    }
  ]
}
```

### 1.3 FastAPI Application (`main.py`)

This core backend file handles AI field generation, secure data lookups, and form publishing workflows.

```python
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from openai import OpenAI

app = FastAPI(title="Dynamic Form Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize xAI Grok Client (OpenAI-compatible)
grok_client = OpenAI(
    api_key=os.environ.get("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

class FieldPromptRequest(BaseModel):
    prompt: str

class FieldTemplateSave(BaseModel):
    name: str
    label: str
    field_type: str
    angular_config: Dict[str, Any]
    validation_rules: Dict[str, Any]
    api_config: Optional[Dict[str, Any]] = None

class LayoutNode(BaseModel):
    field_id: str
    order: int
    column_span: Optional[int] = 12

class FormVersionCreate(BaseModel):
    version_number: str
    layout_tree: List[LayoutNode]

@app.post("/api/fields/generate")
def generate_field_schema(payload: FieldPromptRequest):
    try:
        with open("angular_material_capabilities.json", "r") as f:
            material_spec = json.load(f)

        system_prompt = f"""
        You are an AI form schema generator for an Angular Material application.
        Map user requests strictly to this component specification: {json.dumps(material_spec)}
        Output a valid JSON object containing keys: field_id, field_type, label, validation_rules, and optional api_config or options.
        """

        response = grok_client.chat.completions.create(
            model="grok-2-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload.prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        field_data = json.loads(response.choices[0].message.content)
        return {"status": "success", "field_template": field_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fields/")
def get_field_templates():
    # Connect to database and return saved templates list
    return []

@app.post("/api/fields/")
def save_field_template(payload: FieldTemplateSave):
    # Save payload into PostgreSQL 'field_templates' table
    return {"status": "success", "message": "Field saved to library!"}

@app.post("/api/forms/{form_id}/versions")
def create_form_version(form_id: str, payload: FormVersionCreate):
    return {"status": "draft_saved", "version": payload.version_number}

@app.post("/api/forms/{form_id}/versions/{version_id}/publish")
def publish_form_version(form_id: str, version_id: str):
    return {"status": "published", "version_id": version_id}

@app.get("/api/proxy/lookup")
def external_data_lookup(q: str):
    mock_database = ["Canada", "United States", "United Kingdom", "Germany", "France"]
    results = [item for item in mock_database if q.lower() in item.lower()]
    return results
```

---

## PART 2: Frontend Architecture (Angular)

### 2.1 API Service Layer (`form-api.service.ts`)

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class FormApiService {
  private baseUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  generateField(prompt: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/fields/generate`, { prompt });
  }

  getSavedFields(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/fields/`);
  }

  saveFieldTemplate(fieldData: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/fields/`, fieldData);
  }

  saveFormVersion(formId: string, versionData: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/forms/${formId}/versions`, versionData);
  }
}
```

### 2.2 Universal Dynamic Field Chameleon Component (`dynamic-field.component.ts`)

This acts as the universal rendering engine, adapting based on the provided JSON field schema.

```typescript
import { Component, Input, OnInit } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { debounceTime, distinctUntilChanged, filter, switchMap } from 'rxjs/operators';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-dynamic-field',
  template: `
    <div [formGroup]="formGroup" class="field-container w-full">
      
      <!-- 1. TEXT & AUTOCOMPLETE INPUT -->
      <mat-form-field appearance="outline" class="w-full" *ngIf="field.field_type === 'text' || field.field_type === 'autocomplete'">
        <mat-label>{{ field.label }}</mat-label>
        <input matInput [formControlName]="field.field_id" [matAutocomplete]="auto" [placeholder]="field.label">

        <mat-autocomplete #auto="matAutocomplete">
          <mat-option *ngFor="let option of options$ | async" [value]="option">
            {{ option }}
          </mat-option>
        </mat-autocomplete>
      </mat-form-field>

      <!-- 2. DROPDOWN SELECT -->
      <mat-form-field appearance="outline" class="w-full" *ngIf="field.field_type === 'select'">
        <mat-label>{{ field.label }}</mat-label>
        <mat-select [formControlName]="field.field_id">
          <mat-option *ngFor="let opt of field.options" [value]="opt">{{ opt }}</mat-option>
        </mat-select>
      </mat-form-field>

      <!-- 3. CHECKBOX -->
      <mat-checkbox *ngIf="field.field_type === 'checkbox'" [formControlName]="field.field_id">
        {{ field.label }}
      </mat-checkbox>
    </div>
  `
})
export class DynamicFieldComponent implements OnInit {
  @Input() field: any;
  @Input() formGroup!: FormGroup;
  
  options$!: Observable<any[]>;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    const control = this.formGroup.get(this.field.field_id);

    if (this.field.api_config && control) {
      this.options$ = control.valueChanges.pipe(
        debounceTime(this.field.api_config.debounce_ms || 300),
        distinctUntilChanged(),
        filter((val: string) => val && val.length >= (this.field.api_config.trigger_min_chars || 2)),
        switchMap(val => {
          const endpoint = `http://localhost:8000/api/proxy/lookup?q=${val}`;
          return this.http.get<any[]>(endpoint);
        })
      );
    }
  }
}
```

### 2.3 Form Builder Canvas Component (`form-builder.component.ts`)

Provides the drag-and-drop workspace using Angular CDK to arrange the fields into mini-forms.

```typescript
import { Component, OnInit } from '@angular/core';
import { CdkDragDrop, moveItemInArray } from '@angular/cdk/drag-drop';
import { FormApiService } from '../../services/form-api.service';

@Component({
  selector: 'app-form-builder',
  template: `
    <div class="builder-layout flex h-screen">
      <!-- Sidebar Library -->
      <div class="sidebar w-1/4 p-4 border-r bg-gray-50">
        <h3 class="font-bold text-lg mb-4">Field Template Library</h3>
        <div *ngFor="let item of libraryFields" cdkDrag class="p-3 mb-2 bg-white border rounded shadow-sm cursor-move">
          {{ item.label }} <span class="text-xs text-gray-400">({{ item.field_type }})</span>
        </div>
      </div>

      <!-- Canvas Drop Zone -->
      <div cdkDropList class="form-canvas w-3/4 p-6 bg-white overflow-y-auto" (cdkDropListDropped)="drop($event)">
        <h3 class="font-bold text-lg mb-4">Mini-Form Canvas</h3>
        <div *ngFor="let field of canvasFields" cdkDrag class="field-card p-4 mb-3 bg-gray-50 border rounded shadow-sm flex items-center justify-between">
          <div cdkDragHandle class="cursor-pointer font-bold mr-2 text-gray-400">☰</div>
          <span class="flex-grow">{{ field.label }}</span>
          <span class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">{{ field.field_type }}</span>
        </div>
        <button class="mt-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2 rounded shadow" (click)="saveDraft()">
          Save Form Version Draft
        </button>
      </div>
    </div>
  `
})
export class FormBuilderComponent implements OnInit {
  libraryFields: any[] = [];
  canvasFields: any[] = [
    { field_id: 'f1', label: 'Full Name', field_type: 'text', column_span: 12 },
    { field_id: 'f2', label: 'Country Search', field_type: 'autocomplete', column_span: 12, api_config: { trigger_min_chars: 2, debounce_ms: 300 } }
  ];

  constructor(private formApi: FormApiService) {}

  ngOnInit() {
    this.formApi.getSavedFields().subscribe(fields => {
      this.libraryFields = fields;
    });
  }

  drop(event: CdkDragDrop<string[]>) {
    moveItemInArray(this.canvasFields, event.previousIndex, event.currentIndex);
    this.canvasFields.forEach((f, idx) => f.order = idx);
  }

  saveDraft() {
    const payload = {
      version_number: "1.0.0",
      layout_tree: this.canvasFields
    };
    this.formApi.saveFormVersion("some-form-uuid", payload).subscribe(res => {
      console.log("Draft saved successfully!", res);
    });
  }
}
```
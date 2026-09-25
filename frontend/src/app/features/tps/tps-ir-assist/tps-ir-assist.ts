import { ChangeDetectionStrategy, ChangeDetectorRef, Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TpsApiService, TpsIr, TpsPublishedForm } from '../../../core/services/tps-api.service';
import { createSessionId } from '../../../core/utils/session-id';

interface AssistMessage {
  role: 'user' | 'assistant' | 'system';
  text: string;
}

@Component({
  selector: 'app-tps-ir-assist',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './tps-ir-assist.html',
  styleUrl: './tps-ir-assist.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TpsIrAssistComponent {
  private readonly api = inject(TpsApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);

  @Input() ir: TpsIr | null = null;
  @Output() readonly formAssigned = new EventEmitter<void>();
  messages: AssistMessage[] = [];
  prompt = '';
  isContextLoaded = false;
  formUnavailable = false;
  isSending = false;
  error = '';
  publishedForms: TpsPublishedForm[] = [];
  pendingForm: TpsPublishedForm | null = null;
  private sessionId = createSessionId('tps-ir');

  loadContext(): void {
    if (!this.ir) return;
    this.isSending = true;
    this.error = '';
    this.api.loadIrAssistantContext(this.ir.ir_number, this.sessionId, this.ir).subscribe({
      next: () => {
        this.isContextLoaded = true;
        this.isSending = false;
        this.messages = [{ role: 'system', text: `IR context loaded for ${this.ir!.ir_number} and ${this.ir!.customer_name}. Ask a question about this implementation request.` }];
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.isSending = false;
        this.error = error?.error?.detail ?? 'The IR context could not be loaded.';
        this.changeDetector.markForCheck();
      },
    });
  }

  send(): void {
    if (!this.ir || !this.isContextLoaded || this.isSending || this.pendingForm || !this.prompt.trim()) return;
    const prompt = this.prompt.trim();
    this.prompt = '';
    this.messages = [...this.messages, { role: 'user', text: prompt }];
    this.isSending = true;
    this.error = '';
    this.api.askIrAssistantSession(this.ir.ir_number, this.sessionId, prompt).subscribe({
      next: response => {
        this.messages = [...this.messages, { role: 'assistant', text: response.assistant_message }];
        this.publishedForms = response.published_forms ?? [];
        this.pendingForm = response.pending_form ?? null;
        this.formUnavailable = !this.publishedForms.length && !this.pendingForm;
        this.isSending = false;
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'TPS IR Assist could not answer right now.';
        this.isSending = false;
        this.changeDetector.markForCheck();
      },
    });
  }

  confirmPendingForm(): void {
    if (!this.ir || !this.pendingForm || this.isSending) return;
    this.isSending = true;
    this.api.assignFormToIr(this.ir.ir_number, this.pendingForm).subscribe({
      next: () => {
        this.messages = [...this.messages, { role: 'assistant', text: `Confirmed. **${this.pendingForm!.title}** has been assigned to this IR and a draft submission was created.` }];
        this.pendingForm = null;
        this.isSending = false;
        this.formAssigned.emit();
        this.changeDetector.markForCheck();
      },
      error: error => {
        this.error = error?.error?.detail ?? 'The form could not be assigned.';
        this.isSending = false;
        this.changeDetector.markForCheck();
      },
    });
  }

  cancelPendingForm(): void {
    this.pendingForm = null;
    this.messages = [...this.messages, { role: 'system', text: 'Form assignment cancelled.' }];
  }

  newSession(): void {
    this.sessionId = createSessionId('tps-ir');
    this.messages = [];
    this.prompt = '';
    this.isContextLoaded = false;
    this.pendingForm = null;
    this.publishedForms = [];
    this.formUnavailable = false;
    this.error = '';
    this.isSending = false;
    this.changeDetector.markForCheck();
  }

  handleEnter(event: Event): void {
    if (!(event as KeyboardEvent).shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  formatMessage(text: string): string {
    const escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    return escaped
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/^- /gm, '• ')
      .replace(/\n/g, '<br>');
  }
}

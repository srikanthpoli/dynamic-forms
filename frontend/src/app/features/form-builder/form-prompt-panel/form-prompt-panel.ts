import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-form-prompt-panel',
  standalone: true,
  imports: [FormsModule, MatButtonModule, NgClass],
  templateUrl: './form-prompt-panel.html',
  styleUrl: './form-prompt-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FormPromptPanelComponent {
  @Input() messages: { role: 'user' | 'agent'; text: string }[] = [];
  @Input() isSending = false;
  @Output() readonly promptSubmitted = new EventEmitter<string>();
  @Output() readonly newSessionRequested = new EventEmitter<void>();

  prompt = 'Build a customer registration form using the available full name and email fields.';
  isMinimized = false;

  toggleMinimized(): void {
    this.isMinimized = !this.isMinimized;
  }

  submit(): void {
    if (this.isSending) return;
    const value = this.prompt.trim();
    if (value) {
      this.prompt = '';
      this.promptSubmitted.emit(value);
    }
  }

  handleEnter(event: Event): void {
    if (!(event as KeyboardEvent).shiftKey) {
      event.preventDefault();
      this.submit();
    }
  }
}

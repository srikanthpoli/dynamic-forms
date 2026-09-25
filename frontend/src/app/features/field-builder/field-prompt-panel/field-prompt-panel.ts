import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

@Component({
  selector: 'app-field-prompt-panel',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, NgClass],
  templateUrl: './field-prompt-panel.html',
  styleUrl: './field-prompt-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldPromptPanelComponent {
  @Input() messages: { role: 'user' | 'agent'; text: string }[] = [];
  @Input() isSending = false;
  @Output() readonly promptSubmitted = new EventEmitter<string>();
  @Output() readonly newSessionRequested = new EventEmitter<void>();
  prompt = 'Create a required customer email field with a maximum length of 120 characters.';
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

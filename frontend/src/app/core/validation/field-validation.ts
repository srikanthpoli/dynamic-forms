import { AbstractControl, ValidatorFn, Validators } from '@angular/forms';

type RuleValue = unknown;
type RuleFactory = (value: RuleValue) => ValidatorFn;
type ErrorMessage = (error: Record<string, unknown>) => string;

interface ValidationRuleDefinition {
  create: RuleFactory;
  message: ErrorMessage;
}

const ruleDefinitions: Record<string, ValidationRuleDefinition> = {
  required: {
    create: () => Validators.required,
    message: () => 'A value is required.',
  },
  requiredTrue: {
    create: () => Validators.requiredTrue,
    message: () => 'This must be accepted.',
  },
  email: {
    create: () => Validators.email,
    message: () => 'Enter a valid email address.',
  },
  minlength: {
    create: value => Validators.minLength(Number(value)),
    message: error => `Use at least ${error['requiredLength']} characters.`,
  },
  maxlength: {
    create: value => Validators.maxLength(Number(value)),
    message: error => `Use no more than ${error['requiredLength']} characters.`,
  },
  min: {
    create: value => Validators.min(Number(value)),
    message: error => `Use a value of at least ${error['min']}.`,
  },
  max: {
    create: value => Validators.max(Number(value)),
    message: error => `Use a value of no more than ${error['max']}.`,
  },
  pattern: {
    create: value => Validators.pattern(String(value)),
    message: () => 'The value does not match the required format.',
  },
};

export function buildFieldValidators(rules: Record<string, unknown>): ValidatorFn[] {
  return Object.entries(rules)
    .filter(([name, value]) => Boolean(value) && ruleDefinitions[name])
    .map(([name, value]) => ruleDefinitions[name].create(value));
}

export function getValidationMessage(control: AbstractControl, messages: Record<string, string> = {}): string {
  const errors = control.errors;
  if (!errors) return 'All configured validations pass.';

  for (const name of Object.keys(errors)) {
    if (messages[name]) return messages[name];
    const definition = ruleDefinitions[name];
    if (definition) return definition.message(errors[name] as Record<string, unknown>);
  }

  return 'Review the field value.';
}

export function getConfiguredValidationMessages(
  rules: Record<string, unknown>,
  messages: Record<string, string> = {},
  fieldLabel = 'This field',
): string[] {
  return Object.keys(rules).map(name => {
    if (messages[name]) return messages[name];
    const value = rules[name];
    switch (name) {
      case 'required': return `${fieldLabel} is required.`;
      case 'requiredTrue': return `${fieldLabel} must be accepted.`;
      case 'email': return `${fieldLabel} must be a valid email address.`;
      case 'minlength': return `${fieldLabel} must contain at least ${value} characters.`;
      case 'maxlength': return `${fieldLabel} must contain no more than ${value} characters.`;
      case 'min': return `${fieldLabel} must be at least ${value}.`;
      case 'max': return `${fieldLabel} must be no more than ${value}.`;
      case 'pattern': return `${fieldLabel} must match the required format.`;
      default: return `${fieldLabel} must satisfy the ${name} rule.`;
    }
  });
}

export function getAngularValidatorsCode(rules: Record<string, unknown>): string {
  const validators = Object.entries(rules)
    .filter(([name, value]) => Boolean(value) && ruleDefinitions[name])
    .map(([name, value]) => {
      if (name === 'requiredTrue') return 'Validators.requiredTrue';
      if (name === 'email' || name === 'required') return `Validators.${name}`;
      if (name === 'pattern') return `Validators.pattern(${JSON.stringify(value)})`;
      if (name === 'minlength') return `Validators.minLength(${Number(value)})`;
      if (name === 'maxlength') return `Validators.maxLength(${Number(value)})`;
      if (name === 'min' || name === 'max') return `Validators.${name}(${Number(value)})`;
      return null;
    })
    .filter((value): value is string => value !== null);
  return validators.length ? `[${validators.join(', ')}]` : '[]';
}

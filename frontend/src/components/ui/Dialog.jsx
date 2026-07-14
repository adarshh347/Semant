// Radix Dialog, dressed in the Semant plum v1.3 tokens.
// Headless behaviour (focus trap, Esc, scroll-lock, a11y) from Radix; every
// pixel of surface/border/shadow comes from our CSS variables.
import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import './Dialog.css';

export const Dialog = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogClose = RadixDialog.Close;

export function DialogContent({
  title,
  description,
  children,
  className = '',
  size = 'md',
  showClose = true,
  ...props
}) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="ui-dialog-overlay" />
      <RadixDialog.Content className={`ui-dialog ui-dialog--${size} ${className}`} {...props}>
        <header className="ui-dialog-head">
          <div>
            {/* Title is required for a11y; description is optional. */}
            <RadixDialog.Title className="ui-dialog-title">{title}</RadixDialog.Title>
            {description && (
              <RadixDialog.Description className="ui-dialog-desc">{description}</RadixDialog.Description>
            )}
          </div>
          {showClose && (
            <RadixDialog.Close className="ui-dialog-close" aria-label="Close">
              <X size={18} />
            </RadixDialog.Close>
          )}
        </header>
        <div className="ui-dialog-body">{children}</div>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

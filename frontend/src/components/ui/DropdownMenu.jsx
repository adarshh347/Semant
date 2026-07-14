// Radix DropdownMenu, themed to Semant plum v1.3.
import * as RadixMenu from '@radix-ui/react-dropdown-menu';
import './DropdownMenu.css';

export const DropdownMenu = RadixMenu.Root;
export const DropdownMenuTrigger = RadixMenu.Trigger;

export function DropdownMenuContent({ children, align = 'end', sideOffset = 6, className = '', ...props }) {
  return (
    <RadixMenu.Portal>
      <RadixMenu.Content
        className={`ui-menu ${className}`}
        align={align}
        sideOffset={sideOffset}
        {...props}
      >
        {children}
      </RadixMenu.Content>
    </RadixMenu.Portal>
  );
}

export function DropdownMenuItem({ children, className = '', ...props }) {
  return (
    <RadixMenu.Item className={`ui-menu-item ${className}`} {...props}>
      {children}
    </RadixMenu.Item>
  );
}

export function DropdownMenuLabel({ children }) {
  return <RadixMenu.Label className="ui-menu-label">{children}</RadixMenu.Label>;
}

export function DropdownMenuSeparator() {
  return <RadixMenu.Separator className="ui-menu-sep" />;
}

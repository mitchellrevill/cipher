import React, { type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeadingProps {
  title: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  breadcrumb?: ReactNode;
  actions?: ReactNode;
  bleed?: boolean;
  sticky?: boolean;
  titleElement?: "h1" | "div" | "span";
  className?: string;
}

export function PageHeading({
  title,
  description,
  icon,
  breadcrumb,
  actions,
  bleed = true,
  sticky = false,
  titleElement = "h1",
  className,
}: PageHeadingProps) {
  const TitleTag = titleElement;

  // Ensure the icon scales responsively to match title sizes.
  let iconElement: React.ReactNode = icon ?? null;
  if (icon && React.isValidElement(icon)) {
    const iconWithClassName = icon as React.ReactElement<{ className?: string }>;
    const existing = iconWithClassName.props.className ?? "";
    const merged = cn("h-5 w-5 sm:h-6 sm:w-6", existing);
    iconElement = React.cloneElement(iconWithClassName, { className: merged });
  }

  return (
    <div
      className={cn(
        "bg-background border-b border-border px-3 py-3 sm:px-6 sm:py-6",
        bleed && "-mx-4 -mt-4",
        sticky && "sticky top-0 z-40 backdrop-blur supports-[backdrop-filter]:bg-background/80",
        className
      )}
    >
      <div className="w-full max-w-7xl mx-auto">
        <div className="flex items-center justify-between gap-3 sm:gap-4">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {icon ? (
              <div className="p-1.5 sm:p-2 rounded-lg bg-primary/10 text-primary flex-shrink-0 flex items-center justify-center">
                {iconElement}
              </div>
            ) : null}

            <div className="min-w-0 flex-1 space-y-1">
              <TitleTag className="text-lg xs:text-xl sm:text-2xl font-bold truncate">{title}</TitleTag>
              {breadcrumb ? <div className="hidden sm:block">{breadcrumb}</div> : null}
              {description ? <p className="hidden sm:block text-muted-foreground">{description}</p> : null}
            </div>
          </div>

          {actions ? <div className="flex-shrink-0">{actions}</div> : null}
        </div>
      </div>
    </div>
  );
}
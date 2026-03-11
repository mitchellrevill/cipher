import React from "react";
import { Link } from "@tanstack/react-router";
import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem as BreadcrumbListItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export interface SmartBreadcrumbItem {
  label: string;
  href?: string;
  to?: string;
  isCurrentPage?: boolean;
}

interface SmartBreadcrumbProps {
  items: SmartBreadcrumbItem[];
  className?: string;
  maxItems?: number;
  showHome?: boolean;
}

export function SmartBreadcrumb({
  items,
  className,
  maxItems = 3,
  showHome = true,
}: SmartBreadcrumbProps) {
  const allItems: SmartBreadcrumbItem[] = showHome ? [{ label: "Home", to: "/" }, ...items] : items;
  const shouldShowEllipsis = allItems.length > maxItems;
  const displayItems = shouldShowEllipsis ? [allItems[0], ...allItems.slice(-2)] : allItems;
  const hiddenItems = shouldShowEllipsis ? allItems.slice(1, -2) : [];

  return (
    <Breadcrumb className={cn(className)}>
      <BreadcrumbList>
        {displayItems.map((item, index) => {
          const isLast = index === displayItems.length - 1;
          const isEllipsisPosition = shouldShowEllipsis && index === 1;

          return (
            <React.Fragment key={`${item.label}-${index}`}>
              {isEllipsisPosition && hiddenItems.length > 0 ? (
                <>
                  <BreadcrumbListItem>
                    <DropdownMenu>
                      <DropdownMenuTrigger className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-muted">
                        <BreadcrumbEllipsis className="h-4 w-4" />
                        <span className="sr-only">Open breadcrumb menu</span>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        {hiddenItems.map((hiddenItem) => (
                          <DropdownMenuItem key={hiddenItem.label} asChild>
                            {hiddenItem.to ? (
                              <Link to={hiddenItem.to}>{hiddenItem.label}</Link>
                            ) : hiddenItem.href ? (
                              <a href={hiddenItem.href}>{hiddenItem.label}</a>
                            ) : (
                              <span>{hiddenItem.label}</span>
                            )}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </BreadcrumbListItem>
                  <BreadcrumbSeparator />
                </>
              ) : null}

              <BreadcrumbListItem>
                {isLast || item.isCurrentPage ? (
                  <BreadcrumbPage className="max-w-[160px] truncate">{item.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    {item.to ? (
                      <Link to={item.to}>{item.label}</Link>
                    ) : item.href ? (
                      <a href={item.href}>{item.label}</a>
                    ) : (
                      <span>{item.label}</span>
                    )}
                  </BreadcrumbLink>
                )}
              </BreadcrumbListItem>

              {!isLast ? <BreadcrumbSeparator /> : null}
            </React.Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
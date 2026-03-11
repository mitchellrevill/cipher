import { Palette } from "lucide-react";
import { useTheme } from "next-themes";
import { customThemes, systemThemes } from "@/lib/themes";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon">
          <Palette className="h-[1.2rem] w-[1.2rem]" />
          <span className="sr-only">Choose theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>App themes</DropdownMenuLabel>
        {customThemes.map((option) => (
          <DropdownMenuCheckboxItem
            key={option.id}
            checked={theme === option.id}
            onCheckedChange={() => setTheme(option.id)}
          >
            {option.label}
          </DropdownMenuCheckboxItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>System</DropdownMenuLabel>
        {systemThemes.map((option) => (
          <DropdownMenuCheckboxItem
            key={option.id}
            checked={theme === option.id}
            onCheckedChange={() => setTheme(option.id)}
          >
            {option.label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
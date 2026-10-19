import Link from "next/link";
import { cva } from "class-variance-authority";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "ghost" | "ai" | "danger";
type Size = "sm" | "md" | "lg" | "icon";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent-primary text-white shadow-sm hover:bg-accent-hover",
        secondary:
          "border border-border-default bg-surface text-text-primary hover:border-accent-primary/50 hover:bg-background-secondary",
        ghost: "text-text-secondary hover:bg-background-secondary hover:text-text-primary",
        ai: "border border-accent-ai/30 bg-accent-ai/10 text-accent-ai hover:bg-accent-ai/20",
        danger: "bg-error text-white shadow-sm hover:brightness-110",
      },
      size: {
        sm: "h-9 px-3.5 text-sm",
        md: "h-10 px-5 text-sm",
        lg: "h-12 px-7 text-base",
        icon: "h-9 w-9 shrink-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export default function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  loading = false,
  ...props
}: {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: React.ReactNode;
  loading?: boolean;
} & (
  | { as?: "button" } & React.ButtonHTMLAttributes<HTMLButtonElement>
  | { as: "link"; href: string; target?: string; rel?: string }
)) {
  const classes = buttonVariants({ variant, size, className });

  if (props.as === "link") {
    const { href, target, rel } = props;
    return (
      <Link href={href} target={target} rel={rel} className={classes}>
        {children}
      </Link>
    );
  }

  // Default to type="button": inside a <form> a Cancel/secondary button must not
  // submit it (a bare <button> is a submit button). Submit buttons say type="submit".
  const { as: _as, disabled, type = "button", ...rest } = props;
  void _as;
  return (
    <button className={classes} disabled={disabled || loading} type={type} {...rest}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

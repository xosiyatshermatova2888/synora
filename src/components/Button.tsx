import Link from "next/link";
import { cva } from "class-variance-authority";

type Variant = "primary" | "secondary" | "ghost" | "ai";
type Size = "sm" | "md" | "lg";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-accent-primary text-white hover:brightness-110 shadow-lg shadow-accent-primary/20",
        secondary:
          "border border-border-default bg-surface text-text-primary hover:border-accent-primary/60 hover:bg-background-secondary",
        ghost: "text-text-secondary hover:text-text-primary",
        ai: "border border-accent-ai/30 bg-accent-ai/10 text-accent-ai hover:bg-accent-ai/20",
      },
      size: {
        sm: "h-9 px-4 text-sm",
        md: "h-11 px-6 text-sm",
        lg: "h-14 px-8 text-base",
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
  ...props
}: {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: React.ReactNode;
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

  const { as: _as, ...rest } = props;
  void _as;
  return (
    <button className={classes} {...rest}>
      {children}
    </button>
  );
}

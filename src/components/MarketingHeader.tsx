import Container from "@/components/Container";

export default function MarketingHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <section className="pt-28 pb-12 sm:pt-36 sm:pb-16">
      <Container className="max-w-3xl text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-primary">
          {eyebrow}
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          {title}
        </h1>
        <p className="mt-4 text-lg text-text-secondary">{subtitle}</p>
      </Container>
    </section>
  );
}
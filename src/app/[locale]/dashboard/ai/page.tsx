"use client";

import { Sparkles } from "lucide-react";
import ComingSoon from "@/components/dashboard/ComingSoon";

export default function AiAssistantPage() {
  return <ComingSoon kind="ai" ctaHref="/dashboard/reports" icon={Sparkles} />;
}
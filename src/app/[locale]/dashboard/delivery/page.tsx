"use client";

import { Truck } from "lucide-react";
import ComingSoon from "@/components/dashboard/ComingSoon";

export default function DeliveryPage() {
  return <ComingSoon kind="delivery" ctaHref="/dashboard/orders" icon={Truck} />;
}
import { Badge } from "@/components/ui/badge";

interface LeadScoreBadgeProps {
  score: number;
}

export function LeadScoreBadge({ score }: LeadScoreBadgeProps) {
  let variant: "success" | "warning" | "danger";
  let label: string;

  if (score >= 70) {
    variant = "success";
    label = "Warm";
  } else if (score >= 40) {
    variant = "warning";
    label = "Tiede";
  } else {
    variant = "danger";
    label = "Froid";
  }

  return (
    <Badge variant={variant}>
      {score} - {label}
    </Badge>
  );
}

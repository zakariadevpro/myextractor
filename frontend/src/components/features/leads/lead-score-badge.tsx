import { Badge } from "@/components/ui/badge";

interface LeadScoreBadgeProps {
  score: number;
}

export function LeadScoreBadge({ score }: LeadScoreBadgeProps) {
  let variant: "success" | "warning" | "danger";
  let label: string;

  if (score > 70) {
    variant = "success";
    label = "Excellent";
  } else if (score >= 40) {
    variant = "warning";
    label = "Moyen";
  } else {
    variant = "danger";
    label = "Faible";
  }

  return (
    <Badge variant={variant}>
      {score} - {label}
    </Badge>
  );
}

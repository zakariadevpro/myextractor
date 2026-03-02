"use client";

import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeadFilters, SuggestedSegment } from "@/types/lead";

interface SuggestedSegmentsProps {
  segments: SuggestedSegment[];
  onApply: (filters: LeadFilters) => void;
}

export function SuggestedSegments({ segments, onApply }: SuggestedSegmentsProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Segments Intelligents
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {segments.map((segment) => (
          <div key={segment.code} className="rounded-lg border border-border p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-900">{segment.label}</p>
              <Badge variant="outline">{segment.count}</Badge>
            </div>
            <p className="mb-3 text-xs text-muted-foreground">{segment.description}</p>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() =>
                onApply({
                  page: 1,
                  page_size: 20,
                  ...(segment.filters as LeadFilters),
                })
              }
            >
              Appliquer
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

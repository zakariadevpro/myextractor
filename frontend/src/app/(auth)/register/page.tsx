"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const registerSchema = z.object({
  first_name: z
    .string()
    .min(1, "Le prenom est requis")
    .min(2, "Le prenom doit contenir au moins 2 caracteres"),
  last_name: z
    .string()
    .min(1, "Le nom est requis")
    .min(2, "Le nom doit contenir au moins 2 caracteres"),
  email: z
    .string()
    .min(1, "L'email est requis")
    .email("Adresse email invalide"),
  password: z
    .string()
    .min(1, "Le mot de passe est requis")
    .min(8, "Le mot de passe doit contenir au moins 8 caracteres"),
  organization_name: z
    .string()
    .min(1, "Le nom de l'organisation est requis")
    .min(2, "Le nom doit contenir au moins 2 caracteres"),
});

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      organization_name: "",
    },
  });

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    try {
      await registerUser(data);
      toast.success("Compte cree avec succes !");
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(
        err?.response?.data?.detail ||
          "Erreur lors de la creation du compte. Veuillez reessayer."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">Creer un compte</CardTitle>
        <p className="text-sm text-muted-foreground">
          Commencez a extraire des leads B2B en quelques minutes
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input
              id="first_name"
              label="Prenom"
              type="text"
              placeholder="Jean"
              error={errors.first_name?.message}
              {...register("first_name")}
            />
            <Input
              id="last_name"
              label="Nom"
              type="text"
              placeholder="Dupont"
              error={errors.last_name?.message}
              {...register("last_name")}
            />
          </div>
          <Input
            id="email"
            label="Adresse email"
            type="email"
            placeholder="vous@entreprise.com"
            error={errors.email?.message}
            {...register("email")}
          />
          <Input
            id="password"
            label="Mot de passe"
            type="password"
            placeholder="Minimum 8 caracteres"
            error={errors.password?.message}
            {...register("password")}
          />
          <Input
            id="organization_name"
            label="Nom de l'entreprise"
            type="text"
            placeholder="Mon Entreprise SAS"
            error={errors.organization_name?.message}
            {...register("organization_name")}
          />
          <Button
            type="submit"
            className="w-full"
            size="lg"
            isLoading={isLoading}
          >
            Creer mon compte
          </Button>
        </form>
        <div className="mt-6 text-center text-sm text-slate-600">
          Deja un compte ?{" "}
          <Link
            href="/login"
            className="font-medium text-primary hover:text-primary-700"
          >
            Se connecter
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

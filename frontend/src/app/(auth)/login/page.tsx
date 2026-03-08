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

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "L'email est requis")
    .email("Adresse email invalide"),
  password: z
    .string()
    .min(1, "Le mot de passe est requis")
    .min(6, "Le mot de passe doit contenir au moins 6 caracteres"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    try {
      await login(data);
      toast.success("Connexion reussie !");
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(
        err?.response?.data?.detail || "Erreur de connexion. Verifiez vos identifiants."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">Connexion</CardTitle>
        <p className="text-sm text-muted-foreground">
          Connectez-vous a votre compte Winaity Extractor
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
            placeholder="Votre mot de passe"
            error={errors.password?.message}
            {...register("password")}
          />
          <Button
            type="submit"
            className="w-full"
            size="lg"
            isLoading={isLoading}
          >
            Se connecter
          </Button>
        </form>
        <div className="mt-6 text-center text-sm text-slate-600">
          Pas encore de compte ?{" "}
          <Link
            href="/register"
            className="font-medium text-primary hover:text-primary-700"
          >
            Creer un compte
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

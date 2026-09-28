// O PAULUS.exe: o que o atalho abre.
//
// Abre o programa com o Python que vem junto (python\pythonw.exe, sem janela
// de terminal) e diz onde ficam os dados e os modelos baixados - fora da
// pasta do programa, em %LOCALAPPDATA%\PAULUS. Assim instalar uma versão nova
// troca o programa e não toca em nada do escritório.
//
// Compilado pelo tools\instalador\construir.py com o csc.exe que já vem no
// Windows (.NET Framework 4): nada para instalar, nada para pagar.

using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Lancador
{
    [STAThread]
    static int Main(string[] args)
    {
        string raiz = AppDomain.CurrentDomain.BaseDirectory;
        string pythonw = Path.Combine(raiz, "python", "pythonw.exe");
        string script = Path.Combine(raiz, "app", "src", "desktop.py");
        if (!File.Exists(pythonw) || !File.Exists(script))
        {
            MessageBox.Show(
                "A instalação do PAULUS está incompleta: não achei " + (File.Exists(pythonw) ? script : pythonw) +
                ".\n\nInstale o PAULUS de novo. Os seus dados ficam em " +
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PAULUS") +
                " e não são apagados pela reinstalação.",
                "PAULUS", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        string casa = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PAULUS");
        // O que veio junto (o "--perguntar <arquivo>" do botão direito no
        // Explorer) segue para o programa, cada um entre aspas.
        string argumentos = "\"" + script + "\"";
        foreach (string a in args)
            argumentos += " \"" + a.Replace("\"", "\\\"") + "\"";
        var info = new ProcessStartInfo(pythonw, argumentos)
        {
            UseShellExecute = false,
            // Fora da pasta do programa: o que o PAULUS abre herda esta pasta, e
            // um processo "dentro" dela impede o instalador de atualizar.
            WorkingDirectory = casa,
        };
        // Quem já definiu (a base de demonstração, um teste) manda.
        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("PAULUS_DADOS")))
            info.EnvironmentVariables["PAULUS_DADOS"] = Path.Combine(casa, "dados");
        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("PAULUS_MODELOS")))
            info.EnvironmentVariables["PAULUS_MODELOS"] = Path.Combine(casa, "modelos");
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        info.EnvironmentVariables["PAULUS_INSTALADO"] = "1";

        try
        {
            Directory.CreateDirectory(casa);
            Directory.CreateDirectory(info.EnvironmentVariables["PAULUS_DADOS"]);
            Directory.CreateDirectory(info.EnvironmentVariables["PAULUS_MODELOS"]);
            Process.Start(info);
        }
        catch (Exception e)
        {
            MessageBox.Show("Não consegui abrir o PAULUS: " + e.Message, "PAULUS", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}

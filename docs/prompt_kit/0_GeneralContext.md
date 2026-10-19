#  General Context:
El manejo de Proyectos del Portafolio de la Empresa PepAIDummy se hace a través de la plataforma ServiceNow en su modulo de Strategic Portfolio Management. 
Se asume que se usa la estructura de datos Out Of the Box (OOB).
Se require tener un proceso que sea autónomo y que realice las siguientes tareas:
1.	Conectar con la Base de Datos Transaccional Replica en un RDBMs local.
2.	Leer las tablas de Projects y Status Reports.
3.	Procesar la información y definir el estado actual del proyecto junto con el cumplimiento de estándares de calidad mínimos. Esto lo conoceremos como el OverAll Status Report
4.	Una vez teniendo el OverAll Status Report, se requiere:
i.	Poner a disposición una serie de KPIs sobre el estado del proyecto.
ii.	Enviar de manera automática un correo al Project Manager (PM) con frecuencia diaria sobre el SR de sus proyectos asignados.
iii.	Enviar de manera automática un chat de Telegram con el aviso al Project Manager (PM) con frecuencia diaria sobre el SR de sus proyectos asignados.
iv.	Se debe de construir un sitio web en donde se podrá consultar un Dashboard que contenga los KPIs relecvantes asocioados a un proyecto/Programa/Portafolio definidos.
v.	El PM junto con el Program Manager (PgM) y/o Portafolio Manager (PfM) podrá consultar bajo demanda el SR de los proyectos indicados de manera individual o bien a nivel Programa o Portafolio desde un BOT en Telegram.

> Nota (2026-10-18): el requisito 4.ii (correo) quedó fuera por falta de servidor SMTP; los requisitos 4.iii y 4.v se
> implementan por Telegram. Ver `PROMPT_MAESTRO.md` para la versión vigente de todas las instrucciones.

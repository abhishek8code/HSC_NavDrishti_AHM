using System;
using Pomelo.EntityFrameworkCore.MySql.Infrastructure;
using Microsoft.EntityFrameworkCore;
var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllersWithViews();
builder.Services.AddControllers(); // For API controllers
builder.Services.AddSignalR();

// Register Backend API Service
builder.Services.AddHttpClient<Traffic_Frontend.Services.BackendApiService>();

// Register DbContext for EF Core (commented out - not currently used)
// builder.Services.AddDbContext<Traffic_Frontend.Models.NavDrishtiDbContext>(options =>
//     options.UseMySql(
//         builder.Configuration.GetConnectionString("NavDrishtiDb"),
//         new MySqlServerVersion(new Version(8, 0, 0))
//     )
// );

var app = builder.Build();

// Bind URLs explicitly to improve dev startup stability
var urls = Environment.GetEnvironmentVariable("ASPNETCORE_URLS")
            ?? builder.Configuration["Urls"]
            ?? "http://localhost:5000";
app.Urls.Add(urls);

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}
else
{
    // Disable HTTPS redirection in development
    // app.UseHttpsRedirection();
}
app.UseStaticFiles();

app.UseRouting();

app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.MapControllers(); // Map API controllers

app.MapHub<Traffic_Frontend.Hubs.DashboardHub>("/dashboardHub");

// Add top-level diagnostics to log any host/Startup failures
var logger = app.Services.GetService<ILogger<Program>>();
try
{
    Console.WriteLine($"Starting Traffic_Frontend on {string.Join(", ", app.Urls)}");
    app.Run();
}
catch (Exception ex)
{
    if (logger != null)
    {
        logger.LogCritical(ex, "Host terminated unexpectedly");
    }
    else
    {
        Console.WriteLine("Host terminated unexpectedly: " + ex.ToString());
    }
    throw;
}


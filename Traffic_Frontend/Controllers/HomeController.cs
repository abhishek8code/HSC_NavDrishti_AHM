using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using Traffic_Frontend.Services;

namespace Traffic_Frontend.Controllers
{
    public class HomeController : Controller
    {
        private readonly IConfiguration _configuration;
        private readonly BackendApiService _backendApiService;
        private readonly ILogger<HomeController> _logger;

        public HomeController(IConfiguration configuration, BackendApiService backendApiService, ILogger<HomeController> logger)
        {
            _configuration = configuration;
            _backendApiService = backendApiService;
            _logger = logger;
        }

        public IActionResult Index()
        {
            ViewBag.MapboxAccessToken = _configuration["Mapbox:AccessToken"];
            return View();
        }

        public async Task<IActionResult> Dashboard()
        {
            ViewBag.MapboxAccessToken = _configuration["Mapbox:AccessToken"];
            ViewBag.BackendApiUrl = _configuration["BackendApi:BaseUrl"] ?? "http://localhost:8000";
            
            try
            {
                var projects = await _backendApiService.GetProjectsAsync();
                if (projects != null)
                {
                    ViewBag.Projects = projects;
                }
                else
                {
                    ViewBag.Projects = new List<ProjectDto>();
                }
            }
            catch (Exception ex)
            {
                _logger.LogError($"Failed to fetch projects: {ex.Message}");
                ViewBag.Projects = new List<ProjectDto>();
            }
            
            return View();
        }

        public async Task<IActionResult> ProjectCreation()
        {
            ViewBag.MapboxAccessToken = _configuration["Mapbox:AccessToken"];
            ViewBag.BackendApiUrl = _configuration["BackendApi:BaseUrl"] ?? "http://localhost:8000";

            try
            {
                var projects = await _backendApiService.GetProjectsAsync();
                ViewBag.Projects = projects ?? new List<ProjectDto>();
            }
            catch (Exception ex)
            {
                _logger.LogError($"Failed to fetch projects for ProjectCreation: {ex.Message}");
                ViewBag.Projects = new List<ProjectDto>();
            }

            return View();
        }

        public IActionResult TrafficMap()
        {
            ViewBag.MapboxAccessToken = _configuration["Mapbox:AccessToken"];
            ViewBag.BackendApiUrl = _configuration["BackendApi:BaseUrl"] ?? "http://localhost:8000";
            return View();
        }

        public IActionResult EvidenceViewer(double? lat, double? lon)
        {
            ViewBag.Latitude = lat;
            ViewBag.Longitude = lon;
            ViewBag.BackendApiUrl = _configuration["BackendApi:BaseUrl"] ?? "http://localhost:8000";
            return View();
        }
    }
}


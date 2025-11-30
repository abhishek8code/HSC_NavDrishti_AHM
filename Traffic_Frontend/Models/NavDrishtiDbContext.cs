using Microsoft.EntityFrameworkCore;

namespace Traffic_Frontend.Models
{
    public class NavDrishtiDbContext : DbContext
    {
        public NavDrishtiDbContext(DbContextOptions<NavDrishtiDbContext> options) : base(options) { }
        
        public NavDrishtiDbContext() { }

        protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
        {
            if (!optionsBuilder.IsConfigured)
            {
                // Use your connection string here
                optionsBuilder.UseMySql(
                    "Server=localhost;Database=navdrishti;User=root;Password=AbHi!@*%12;",
                    new MySqlServerVersion(new Version(8, 0, 0))
                );
            }
        }
        public DbSet<Project> Projects { get; set; }
        public DbSet<RoadNetwork> RoadNetworks { get; set; }
        public DbSet<TrafficDynamics> TrafficDynamics { get; set; }
        public DbSet<DamageCluster> DamageClusters { get; set; }
    }

    public class Project
    {
        public int Id { get; set; }
        public string? Name { get; set; }
        public string? Status { get; set; }
        public DateTime? StartTime { get; set; }
        public DateTime? EndTime { get; set; }
        public double? StartLat { get; set; }
        public double? StartLon { get; set; }
        public double? EndLat { get; set; }
        public double? EndLon { get; set; }
        public string? ResourceAllocation { get; set; }
        public double? EmissionReductionEstimate { get; set; }
        public int? RoadSegmentId { get; set; }
        public RoadNetwork? RoadSegment { get; set; }
    }

    public class RoadNetwork
    {
        public int Id { get; set; }
        public string? Name { get; set; }
        public string? Geometry { get; set; } // WKT or GeoJSON
        public int? BaseCapacity { get; set; }
        public double? RoughnessIndex { get; set; }
    }

    public class TrafficDynamics
    {
        public int Id { get; set; }
        public int? RoadSegmentId { get; set; }
        public RoadNetwork? RoadSegment { get; set; }
        public DateTime? Timestamp { get; set; }
        public double? FlowEntropy { get; set; }
        public string? CongestionState { get; set; }
        public int? VehicleCount { get; set; }
        public double? AverageSpeed { get; set; }
    }

    public class DamageCluster
    {
        public int Id { get; set; }
        public double? CentroidLat { get; set; }
        public double? CentroidLon { get; set; }
        public double? AvgSeverity { get; set; }
        public int? Count { get; set; }
        public int? RoadSegmentId { get; set; }
        public RoadNetwork? RoadSegment { get; set; }
    }
}

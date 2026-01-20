using System;
using System.Collections.Generic;
using System.Linq;

namespace DIFramework
{
    /// <summary>
    /// Custom Dependency Injection Container
    /// Demonstrates: C# generics, reflection, LINQ, design patterns
    /// </summary>
    public class DIContainer
    {
        private readonly Dictionary<Type, ServiceDescriptor> services = new();

        public enum ServiceLifetime
        {
            Transient,  // New instance each time
            Scoped,     // One instance per scope
            Singleton   // One instance globally
        }

        private class ServiceDescriptor
        {
            public Type ServiceType { get; set; }
            public Type ImplementationType { get; set; }
            public ServiceLifetime Lifetime { get; set; }
            public object Instance { get; set; }
            public Func<DIContainer, object> Factory { get; set; }
        }

        /// <summary>
        /// Register a service with transient lifetime
        /// </summary>
        public void AddTransient<TService, TImplementation>() 
            where TImplementation : TService
        {
            services[typeof(TService)] = new ServiceDescriptor
            {
                ServiceType = typeof(TService),
                ImplementationType = typeof(TImplementation),
                Lifetime = ServiceLifetime.Transient
            };
        }

        /// <summary>
        /// Register a service with singleton lifetime
        /// </summary>
        public void AddSingleton<TService, TImplementation>() 
            where TImplementation : TService
        {
            services[typeof(TService)] = new ServiceDescriptor
            {
                ServiceType = typeof(TService),
                ImplementationType = typeof(TImplementation),
                Lifetime = ServiceLifetime.Singleton
            };
        }

        /// <summary>
        /// Resolve a service from the container
        /// </summary>
        public TService Resolve<TService>()
        {
            return (TService)Resolve(typeof(TService));
        }

        private object Resolve(Type serviceType)
        {
            if (!services.TryGetValue(serviceType, out var descriptor))
            {
                throw new InvalidOperationException(
                    $"Service of type {serviceType.Name} is not registered.");
            }

            // Return existing singleton
            if (descriptor.Lifetime == ServiceLifetime.Singleton && 
                descriptor.Instance != null)
            {
                return descriptor.Instance;
            }

            // Create instance
            var instance = CreateInstance(descriptor.ImplementationType);

            // Cache singleton
            if (descriptor.Lifetime == ServiceLifetime.Singleton)
            {
                descriptor.Instance = instance;
            }

            return instance;
        }

        private object CreateInstance(Type type)
        {
            // Get constructor
            var constructor = type.GetConstructors().FirstOrDefault();
            if (constructor == null)
            {
                throw new InvalidOperationException(
                    $"No public constructor found for {type.Name}");
            }

            // Resolve constructor parameters
            var parameters = constructor.GetParameters()
                .Select(param => Resolve(param.ParameterType))
                .ToArray();

            return Activator.CreateInstance(type, parameters);
        }
    }

    // Example services
    public interface ILogger
    {
        void Log(string message);
    }

    public class ConsoleLogger : ILogger
    {
        public void Log(string message)
        {
            Console.WriteLine($"[LOG] {message}");
        }
    }

    public interface IUserService
    {
        void CreateUser(string name);
    }

    public class UserService : IUserService
    {
        private readonly ILogger logger;

        public UserService(ILogger logger)
        {
            this.logger = logger;
        }

        public void CreateUser(string name)
        {
            logger.Log($"Creating user: {name}");
        }
    }

    // Demo
    class Program
    {
        static void Main(string[] args)
        {
            var container = new DIContainer();

            // Register services
            container.AddSingleton<ILogger, ConsoleLogger>();
            container.AddTransient<IUserService, UserService>();

            // Resolve and use
            var userService = container.Resolve<IUserService>();
            userService.CreateUser("John Doe");

            Console.WriteLine("DI Container demo complete!");
        }
    }
}

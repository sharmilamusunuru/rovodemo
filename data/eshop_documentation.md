# eShop Application Documentation

## Overview

The eShop application is a legacy e-commerce platform built on .NET Framework 4.7 running on
Windows Server 2016. It handles product catalog, order processing, customer management,
and payment processing for an online retail operation.

## Architecture

### Current Stack

- **Frontend**: ASP.NET WebForms + jQuery 1.x
- **Backend**: .NET Framework 4.7, C#
- **Database**: SQL Server 2014 (on-premises)
- **Cache**: Windows Memory Cache (in-process)
- **Authentication**: Custom Forms Authentication with SQL membership
- **File Storage**: Local disk (\\fileserver\eshop-uploads)
- **Messaging**: MSMQ for order processing queue
- **Deployment**: IIS 8.5 on Windows Server 2016 VMs

### Components

#### Product Catalog Service
- Manages product listings, categories, and inventory
- Direct SQL queries via ADO.NET (no ORM)
- Images stored on local file server
- Search implemented via SQL LIKE queries

#### Order Processing Service
- Handles order lifecycle (pending → processing → shipped → delivered)
- Synchronous processing via MSMQ
- Order history in SQL Server
- No retry mechanism for failed orders

#### Customer Service
- Customer registration, profile management
- Passwords stored as MD5 hashes (LEGACY - security risk)
- Sessions stored in ASP.NET InProc session state

#### Payment Processing
- Integrates with legacy payment gateway (SOAP-based)
- PCI compliance via network segmentation only
- No tokenization

#### Notification Service
- Email notifications via SMTP relay
- No SMS or push notifications
- Batch processing runs nightly

## Known Issues

1. **Performance**: Product search is slow (full table scans on 2M+ product rows)
2. **Scalability**: Cannot scale horizontally due to in-proc session and local file storage
3. **Security**: MD5 password hashing is deprecated and insecure
4. **Reliability**: MSMQ failures cause lost orders with no recovery mechanism
5. **Observability**: Minimal logging, no distributed tracing, no metrics
6. **Maintenance**: .NET Framework 4.7 and SQL Server 2014 approaching end of support
7. **Deployment**: Manual deployments, no CI/CD pipeline
8. **Cost**: Over-provisioned VMs running at 15-20% average CPU utilization

## Business Requirements

- 99.9% uptime SLA
- Support for 10x traffic spikes during sales events
- Payment Card Industry (PCI) compliance
- GDPR compliance for EU customers
- Same-day order processing
- Mobile-friendly shopping experience

## Current Infrastructure

- 4x Web Server VMs (8 CPU, 32GB RAM each)
- 2x SQL Server VMs (16 CPU, 64GB RAM, 2TB SSD each, Always On AG)
- 1x File Server VM
- 1x Message Queue Server (MSMQ)
- All hosted in on-premises datacenter

## Existing Jira Project

- **Project Key**: ESHOP
- **Board**: eShop Modernization
- **Epic**: Azure Migration (ESHOP-1)

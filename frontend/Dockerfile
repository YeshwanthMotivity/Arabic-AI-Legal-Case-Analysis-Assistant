# Stage 1: Build the React Application
FROM node:18-alpine AS build

WORKDIR /app

# Install dependencies (use npm install to be more lenient than ci)
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

# Copy source code and build
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy built artifacts from the build stage
COPY --from=build /app/build /usr/share/nginx/html

# Remove default Nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]

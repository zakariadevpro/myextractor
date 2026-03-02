FROM node:20-alpine

WORKDIR /app

# Dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copy application
COPY frontend/ .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "-p", "5173"]

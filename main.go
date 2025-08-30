package main

import (
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
)

func loadEnv() {
	err := godotenv.Load(".env")
	if err != nil {
		if os.IsNotExist(err) {
			log.Println("⚠️  Fichier .env non trouvé, utilisation des variables d'environnement système")
		} else {
			log.Printf("⚠️  Impossible de charger .env : %v", err)
		}
	}
}

func getEnvWithDefault(key, defaultValue string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return defaultValue
}

func ping(c *gin.Context) {
	c.Header("Content-Type", "text/plain; charset=utf-8")
	c.String(http.StatusOK, "Pong")
}

func mail(c *gin.Context) {
	// mailboxUUID := c.Param("mailbox_uuid")
	// folderID := c.Param("folder_id")
	// threadID := c.Param("thread_id")

	// var input YourInputModel
	// if err := c.ShouldBindJSON(&input); err != nil {
	//     c.JSON(http.StatusBadRequest, gin.H{"error": "Requête invalide"})
	//     return
	// }
}

func ai(c *gin.Context) {

}
func main() {
	loadEnv()

	gin.SetMode(gin.DebugMode)

	router := gin.Default()

	router.GET("/ping", ping)

	router.POST("/mail/:mailbox_uuid/folder/:folder_id/thread/:thread_id/event_suggestion", mail)

	router.Run("localhost:8080")
}
